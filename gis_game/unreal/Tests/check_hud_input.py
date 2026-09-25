"""Guard the HUD click and helm input contract before an Unreal build."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PAWN = (ROOT / "Source/GISGame/Private/GISBoatPawn.cpp").read_text()
CONTROLLER = (ROOT / "Source/GISGame/Private/GISPlayerController.cpp").read_text()
INPUT = (ROOT / "Config/DefaultInput.ini").read_text()


def function_body(name: str) -> str:
    match = re.search(rf"void AGISBoatPawn::{name}\([^)]*\)\s*\{{(.*?)\n\}}", PAWN, re.S)
    assert match, f"missing {name}"
    return match.group(1)


assert "DefaultViewportMouseCaptureMode=CaptureDuringMouseDown" in INPUT
assert '+ActionMappings=(ActionName="ToggleMap",Key=M)' in INPUT
assert '+ActionMappings=(ActionName="ToggleDataPanel",Key=Tab)' in INPUT
assert '+ActionMappings=(ActionName="TogglePause",Key=Escape)' in INPUT
assert 'SetHideCursorDuringCapture(false)' in CONTROLLER
assert 'bShowMouseCursor = true' in CONTROLLER
assert 'FInputModeGameAndUI' in CONTROLLER

press = function_body("OnMouseHelmPressed")
assert "GetMousePosition" in press
assert "HandlePointerPress" in press
assert press.index("HandlePointerPress") < press.index("bMouseHelmHeld = true"), (
    "HUD must consume a click before tiller drag starts"
)

for action, handler, hud_call in (
    ("ToggleMap", "OnToggleMap", "ToggleMap()"),
    ("ToggleDataPanel", "OnToggleDataPanel", "ToggleDataPanel()"),
):
    assert f'BindAction(TEXT("{action}")' in PAWN
    assert hud_call in function_body(handler)

assert 'BindAxis(TEXT("SheetWheel")' in PAWN
assert 'bMouseHelmHeld && !FMath::IsNearlyZero(Value)' in function_body("OnMouseHelmAxis")
assert re.search(
    r'FInputActionBinding& MousePressBinding\s*=\s*PlayerInputComponent->BindAction\('
    r'TEXT\("MouseHelmHold"\).*?MousePressBinding\.bExecuteWhenPaused\s*=\s*true;',
    PAWN,
    re.S,
), "menu clicks must work while the simulation is paused"
assert 'TogglePauseMenu()' in function_body("OnTogglePause")
print("GIS HUD input contract passed")
