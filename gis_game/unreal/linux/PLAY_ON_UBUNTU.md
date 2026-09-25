# Play Goat Island Skiff on Ubuntu

The Ubuntu download contains the complete Unreal game for **64-bit Intel or AMD computers**. You do not need Unreal Engine, Blender, or a compiler to play it. The game can use an AMD or NVIDIA graphics card with a working Vulkan driver.

## Easy install on Ubuntu

1. Click **Download Ubuntu installer (test build)** on the Lab page. This saves `Goat-Island-Skiff-Ubuntu.deb` in Downloads.
2. Open the downloaded file. If it does not open in **App Center**, right-click it and choose **Open With App Center**.
3. Click **Install** and enter your Ubuntu password when asked.
4. Open **Goat Island Skiff** from the Ubuntu app menu.

The package is for an **amd64/x86_64 Ubuntu desktop**. It places the game under `/opt/goat-island-skiff` and adds an app-menu shortcut. The package does not install or change graphics drivers. Future versions can be installed by opening the newer `.deb` the same way.

## Portable archive (manual option)

The older `Goat-Island-Skiff-Linux.tar.gz` remains available for people who prefer an install without an administrator password:

1. Download the archive and open a Terminal in its Downloads folder.
2. Extract it: `tar -xzf Goat-Island-Skiff-Linux.tar.gz`
3. Enter the folder: `cd Goat-Island-Skiff-Linux`
4. Install for your account: `./install.sh`
5. Open **Goat Island Skiff** from the Ubuntu app menu.

You can also play without installing: extract the archive, enter its folder, and run `./GISGame.sh`. Keep the entire extracted folder together. The app-menu installer copies the game into your home directory, so you may delete the downloaded archive and extracted folder once the installed game works.

## Graphics and system requirements

The game supplies its Unreal runtime and Lake Greenwood assets, but Ubuntu supplies the graphics driver and Vulkan loader. Epic's Unreal 5.8 Linux requirements list an **x86_64 Linux system**, kernel **4.18** or newer, **glibc 2.28** or newer, **AMD RADV 24.2.8** or newer, and **NVIDIA driver 570** or newer. These are engine guidelines; game performance still depends on the specific computer.

On an **NVIDIA** Ubuntu computer, run Software Updater first. If the game cannot use the card, open **Additional Drivers**, choose Ubuntu's recommended NVIDIA desktop driver, apply it, and restart. Ubuntu's driver tool selects the correct branch for the card; the game's `.deb` does not install it.

On an **AMD** Ubuntu computer, install current system updates first. Ubuntu 24.04 LTS with current updates is the simplest target because Ubuntu 22.04's standard Mesa package is older than Epic's listed RADV version. If Vulkan support is missing, Ubuntu provides it through `libvulkan1` and `mesa-vulkan-drivers`; the optional `vulkan-tools` package provides `vulkaninfo` for checking the driver. For example:

```bash
sudo apt update
sudo apt install libvulkan1 mesa-vulkan-drivers vulkan-tools
vulkaninfo --summary
```

The installer does not change graphics drivers. If `vulkaninfo` shows a software renderer such as **llvmpipe** instead of the AMD GPU, the game is unlikely to run well until Ubuntu uses the hardware driver. On Ubuntu 22.04, the installed Mesa version may need updating to meet Epic's RADV minimum. If the installed game does not start, run `goat-island-skiff` in a Terminal and save the error text. For the portable archive, run `./GISGame.sh` from a Terminal in its extracted folder instead.

## Basic controls

- Hold the left mouse button and drag to move the tiller. The bow turns the opposite way while sailing ahead.
- Scroll the mouse wheel to trim or ease the sail.
- Press **M** for the lake map, **V** to switch camera, and **Esc** for settings or to quit.

This is a sailing game, **not a navigation chart**. Lake depths, hazards, live water levels, and bridge clearances are not verified.

Sources: [Epic's Linux requirements](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine), [Ubuntu's App Center help](https://ubuntu.com/desktop/docs/en/24.04/explanation/snap-and-deb-packages/), [Ubuntu's NVIDIA driver instructions](https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/), [Ubuntu's Mesa Vulkan driver package](https://packages.ubuntu.com/en/noble-updates/mesa-vulkan-drivers).
