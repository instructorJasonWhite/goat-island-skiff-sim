# Play Goat Island Skiff on Ubuntu

This download contains the complete Unreal game for **64-bit Intel or AMD Linux computers**. You do not need Unreal Engine, Blender, or a compiler to play it. An AMD graphics card is fine if its Ubuntu Vulkan driver is new enough.

## Install

1. Download `Goat-Island-Skiff-Linux.tar.gz` and open a Terminal in its Downloads folder.
2. Extract it: `tar -xzf Goat-Island-Skiff-Linux.tar.gz`
3. Enter the folder: `cd Goat-Island-Skiff-Linux`
4. Install for your account: `./install.sh`
5. Open **Goat Island Skiff** from the Ubuntu app menu. No administrator password is needed.

You can also play without installing: extract the archive, enter its folder, and run `./GISGame.sh`. Keep the entire extracted folder together. The app-menu installer copies the game into your home directory, so you may delete the downloaded archive and extracted folder once the installed game works.

## Graphics and system requirements

The game supplies its Unreal runtime and Lake Greenwood assets, but Ubuntu supplies the graphics driver and Vulkan loader. Epic's Unreal 5.8 Linux requirements call for an **x86_64 Linux system**, a kernel at least **4.18**, **glibc 2.28** or newer, and **AMD RADV 24.2.8** or newer for Vulkan (25.0.0 or newer recommended). These are engine requirements; game performance still depends on the specific computer.

On an AMD Ubuntu computer, install current system updates first. If Vulkan support is missing, Ubuntu provides it through `libvulkan1` and `mesa-vulkan-drivers`; the optional `vulkan-tools` package provides `vulkaninfo` for checking the driver. For example:

```bash
sudo apt update
sudo apt install libvulkan1 mesa-vulkan-drivers vulkan-tools
vulkaninfo --summary
```

The installer does not change graphics drivers. If `vulkaninfo` shows a software renderer such as **llvmpipe** instead of the AMD GPU, the game is unlikely to run well until Ubuntu uses the hardware driver. On Ubuntu 22.04, the installed Mesa version may need updating to meet Epic's RADV minimum. If the game does not start, run `./GISGame.sh` from a Terminal in the extracted folder and save the error text.

## Basic controls

- Hold the left mouse button and drag to move the tiller. The bow turns the opposite way while sailing ahead.
- Scroll the mouse wheel to trim or ease the sail.
- Press **M** for the lake map, **V** to switch camera, and **Esc** for settings or to quit.

This is a sailing game, **not a navigation chart**. Lake depths, hazards, live water levels, and bridge clearances are not verified.

Sources: [Epic's Linux requirements](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine), [Ubuntu's Mesa Vulkan driver package](https://packages.ubuntu.com/en/noble-updates/mesa-vulkan-drivers).
