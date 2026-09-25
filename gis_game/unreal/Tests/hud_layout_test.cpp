#include "../Source/GISGame/Public/GISUILayout.h"
#include "../Source/GISGame/Public/GISMenuLayout.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <utility>

int main()
{
    using namespace gis_unreal;
    const auto Wide = make_hud_layout(1280.0, 720.0);
    assert(Wide.MiniMap.Width >= 200.0);
    assert(Wide.ExpandedMap.Width >= Wide.MiniMap.Width * 2.8);
    assert(Wide.ExpandedMap.Width <= 630.0);
    assert(Wide.DataPanel.Right() < Wide.WindPanel.Left);
    assert(Wide.MiniMap.Top > Wide.WindPanel.Bottom());
    assert(Wide.MenuButton.Left > Wide.DataPanel.Right());
    assert(Wide.MenuButton.Right() < Wide.WindPanel.Left);
    assert(hit_test_hud(Wide, false, Wide.MenuButton.Left + 10,
                        Wide.MenuButton.Top + 10) == EHUDHit::MenuButton);
    assert(hit_test_hud(Wide, false, Wide.MiniMap.Left + 20, Wide.MiniMap.Top + 20)
           == EHUDHit::MiniMap);
    assert(hit_test_hud(Wide, false, Wide.DataToggle.Left + 4,
                        Wide.DataToggle.Top + 4) == EHUDHit::DataToggle);
    assert(hit_test_hud(Wide, true, Wide.ExpandedMapClose.Left + 4,
                        Wide.ExpandedMapClose.Top + 4) == EHUDHit::MapClose);
    assert(hit_test_hud(Wide, true, Wide.ExpandedMap.Left + 30,
                        Wide.ExpandedMap.Top + 30) == EHUDHit::MapOverlay);
    assert(hit_test_hud(Wide, false, 640.0, 360.0) == EHUDHit::None);

    const auto Small = make_hud_layout(800.0, 600.0);
    assert(Small.DataPanel.Right() <= Small.WindPanel.Left);
    assert(Small.MiniMap.Right() <= 800.0);
    assert(Small.MiniMap.Bottom() <= 600.0);
    assert(Small.ExpandedMap.Width > Small.MiniMap.Width * 2.4);

    const auto Menu = make_menu_layout(1280.0, 720.0);
    assert(Menu.PausePanel.Left > 0.0);
    assert(Menu.PausePanel.Right() < 1280.0);
    assert(Menu.SettingsPanel.Top > 0.0);
    assert(Menu.SettingsPanel.Bottom() < 720.0);
    assert(Menu.Resume.Bottom() < Menu.OpenSettings.Top);
    assert(Menu.OpenSettings.Bottom() < Menu.Quit.Top);
    assert(Menu.GraphicsRow.Bottom() < Menu.DisplayRow.Top);
    assert(Menu.DisplayRow.Bottom() < Menu.SensitivityRow.Top);
    assert(Menu.SensitivityRow.Bottom() < Menu.Back.Top);

    const auto Center = [](const FHUDRect& R) {
        return std::pair<double, double>{R.Left + R.Width / 2.0,
                                         R.Top + R.Height / 2.0};
    };
    const auto CheckHit = [&](EMenuPage Page, const FHUDRect& R, EMenuHit Hit) {
        const auto [X, Y] = Center(R);
        assert(hit_test_menu(Menu, Page, X, Y) == Hit);
    };
    CheckHit(EMenuPage::Pause, Menu.Resume, EMenuHit::Resume);
    CheckHit(EMenuPage::Pause, Menu.OpenSettings, EMenuHit::OpenSettings);
    CheckHit(EMenuPage::Pause, Menu.Quit, EMenuHit::Quit);
    CheckHit(EMenuPage::Settings, Menu.GraphicsPrevious, EMenuHit::GraphicsPrevious);
    CheckHit(EMenuPage::Settings, Menu.GraphicsNext, EMenuHit::GraphicsNext);
    CheckHit(EMenuPage::Settings, Menu.DisplayPrevious, EMenuHit::DisplayPrevious);
    CheckHit(EMenuPage::Settings, Menu.DisplayNext, EMenuHit::DisplayNext);
    CheckHit(EMenuPage::Settings, Menu.SensitivityPrevious, EMenuHit::SensitivityPrevious);
    CheckHit(EMenuPage::Settings, Menu.SensitivityNext, EMenuHit::SensitivityNext);
    CheckHit(EMenuPage::Settings, Menu.Back, EMenuHit::Back);
    assert(hit_test_menu(Menu, EMenuPage::Pause, 2.0, 2.0) == EMenuHit::Overlay);
    assert(hit_test_menu(Menu, EMenuPage::Settings, 2.0, 2.0) == EMenuHit::Overlay);
    {
        const auto [X, Y] = Center(Menu.Resume);
        assert(hit_test_menu(Menu, EMenuPage::Settings, X, Y) == EMenuHit::Overlay);
    }
    const auto CompactMenu = make_menu_layout(640.0, 360.0);
    assert(CompactMenu.PausePanel.Left >= 0.0);
    assert(CompactMenu.PausePanel.Right() <= 640.0);
    assert(CompactMenu.SettingsPanel.Top >= 0.0);
    assert(CompactMenu.SettingsPanel.Bottom() <= 360.0);
    assert(CompactMenu.SettingsPanel.Left >= 0.0);
    assert(CompactMenu.SettingsPanel.Right() <= 640.0);
    assert(CompactMenu.Back.Bottom() < CompactMenu.SettingsPanel.Bottom());
    std::cout << "HUD layout and interaction geometry passed\n";
}
