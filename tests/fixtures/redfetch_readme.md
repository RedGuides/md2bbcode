![six wizards levitating a package, the word redfetch underneath](https://www.redguides.com/images/redfetchlogo.png)

redfetch is for updating software and scripts for EverQuest that RedGuides recommends, as well as those you "[watch](https://www.redguides.com/community/watched/resources)". It's also open source, how nice.

## Installation

On Windows the easiest way to install redfetch is to [download](https://www.redguides.com/community/resources/redfetch.3177/download) and run [`redfetch.exe`](https://www.redguides.com/community/resources/redfetch.3177/download). (*optional: If you're still on Windows 10 and want a more modern appearance, follow [this guide](https://www.redguides.com/community/threads/redfetch.92998/post-634938) to set [Windows Terminal](https://www.redguides.com/community/threads/redfetch.92998/post-634938) as your default terminal.*)

<details>
<summary>Terminal / Python / Linux</summary>


Make sure you have a recent version of [Python](https://www.python.org/downloads/)

1) **Install pipx**
```bash
python -m pip install --user pipx
```

2) **Make it so you can run packages without having to type "python -m"**
```bash
python -m pipx ensurepath
```

3) **Install redfetch**
```bash
pipx install redfetch
```

When you open a new terminal window you'll be able to run redfetch by typing `redfetch` from the command line. 

</details>

## Usage


### 1) Double-click [`redfetch.exe`](https://www.redguides.com/community/resources/redfetch.3177/download) to run the script. 
Take a moment to consider your configuration and the settings tab.

### 2) Click the big blue "Easy Update" button, and then "Yes" or "Always" on the popup. 
![a screenshot showing the easy update button](https://www.redguides.com/images/redfetchupdate.gif)  
(It's updating *Very Vanilla MQ* and any of its scripts or plugins you have [watched on RedGuides](https://www.redguides.com/community/watched/resources), your licensed resources, and scripts recommended by staff. You can customize this if you like.)

Now you're ready to play EQ with the big boys.

## Add more MQ Scripts
To add more MacroQuest scripts, "watch" them on [www.redguides.com/community/resources](https://www.redguides.com/community/resources), and then click the *Easy Update* button again.

![a screenshot showing the watch button on a resource page](https://www.redguides.com/images/clickwatch.gif)

If there are non-MQ resources you'd like to keep in sync with redfetch, you can add them as a "special resource" in the local settings file, as shown in settings section.

## Command Line
To run redfetch from the command line:

| .exe file | python |
|---------|-----------|
| `.\redfetch.exe update` | `redfetch update` |

![a screenshot showing the command line interface](https://www.redguides.com/images/redfetchcliupdate.gif)

## Command Line Reference

<!-- BEGIN GENERATED CLI REFERENCE -->
> Run `redfetch --help` for the current list, or `redfetch <COMMAND> --help` for a command's options. It looks like:
>
> ### 📦 Resource Management
> - `update` - Update all *watched* and special resources.
>   - `--force` / `-f` - Force re-download of all watched resources.
>   - `--server` / `-s` - Update this server for this run only, without changing your current server (LIVE, TEST, EMU).
> - `download <ID_OR_URL>` - Download a specific resource by ID or URL.
>   - `ID_OR_URL` - RedGuides resource ID or URL
>   - `--force` / `-f` - Force re-download by resetting this resource's download date.
>   - `--server` / `-s` - Download from this server for this run only, without changing your current server (LIVE, TEST, EMU).
> - `check` - Non-interactive update check (for automation.)
>   - `--server` / `-s` - Check this server's env for this run only, without persisting it (LIVE, TEST, EMU).
> - `list` - List resources and dependencies in your local cache.
> - `reset` - Reset download dates for *watched resources* in the database.
>
> ### 🔧 System & Utilities
> - `ui` - Launch the *Terminal User Interface*.
> - `run [SHORTCUT]` - Run a shortcut (e.g. **vvmq**, **eqbcs**, **myseq**). **run** by itself will show a full list.
>   - `SHORTCUT` - Shortcut to run: vvmq, eqbcs, eq, eqgame, etc.
>   - `--server` / `-s` - Run for this server this run only, without changing your current server (LIVE, TEST, EMU).
> - `open [SHORTCUT]` - Open a folder or file (e.g. **downloads**, **eqhost**). **open** by itself will show a full list.
>   - `SHORTCUT` - Folder/file to open: downloads, vvmq, eq, etc.
>   - `--server` / `-s` - Resolve paths for this server this run only, without changing your current server (LIVE, TEST, EMU).
> - `web` - Launch the **RedGuides.com** web interface.
> - `version` - Show version and exit.
> - `uninstall` - Uninstall **redfetch** and clean up data.
> - `logout` - Log out and clear cached token and API cache.
>
> ### 🍔 Configuration
> - `config <SETTING_PATH> <VALUE>` - Update a setting by path and value.
>   - `SETTING_PATH` - Dot-separated setting path (e.g., SPECIAL_RESOURCES.1974.opt_in)
>   - `VALUE` - New value for the setting
>   - `--server` / `-s` - Server to apply the change in (LIVE, TEST, EMU)
> - `server <SERVER>` - Switch the current server/environment to LIVE, TEST, or EMU.
>   - `SERVER` - Server to use: LIVE, TEST, EMU
> - `status` - Show the configuration for the current or specified server.
>   - `--server` / `-s` - Server to show (defaults to current)
>
> ### 📤 Publishing
> - `publish <RESOURCE_ID>` - Publish updates to a **RedGuides** resource.
>   - `RESOURCE_ID` - Existing RedGuides resource ID
>   - `--description <README.md>` / `-d` - Path to a description file (e.g. README.md) to become the overview description.
>   - `--version` / `-v` - New version string (e.g., v1.0.1)
>   - `--message <CHANGELOG.md | MESSAGE>` / `-m` - Path to *CHANGELOG.md* (keep a changelog), other message file, or a direct message string.
>   - `--file <FILE.zip>` / `-f` - Path to your zipped release file
>   - `--domain` - If description or message is a .md file with relative URLs, resolve them to this domain (e.g., https://raw.githubusercontent.com/your/repo/main/)
<!-- END GENERATED CLI REFERENCE -->

The `publish` command also has a [GitHub Action](https://github.com/marketplace/actions/redguides-publish).

## Settings

`settings.local.toml` is found in your configuration directory, which by default is `c:\Users\Public\redfetch\settings.local.toml`. Any keys you add will override their default values in [`settings.toml`](./src/redfetch/settings.toml).

All settings are prefixed with the environment,

- `[DEFAULT]` - encompasses all environments that are not explicitly defined.
- `[LIVE]` - EverQuest Live
- `[TEST]` - EverQuest Test
- `[EMU]` - EverQuest Emulator

### Adding a special resource
To add a "special resource" (a non-MQ resource that you want to keep updated), open `settings.local.toml` and add an entry. You'll need the [resource ID (numbers at the end of the url)](https://www.redguides.com/community/resources/brewalls-everquest-maps.153/) and a target directory. Example:

```toml
[LIVE.SPECIAL_RESOURCES.153]
custom_path = 'C:\Users\Public\Daybreak Game Company\Installed Games\EverQuest\maps\Brewall_Maps'
opt_in = true
```
* Note the use of single quotes around the path, which are required for windows paths.

The above will install Brewall's maps to the EQ maps directory the next time `redfetch update` is run for `LIVE` servers.

### Overwrite protection

If there are local files you don't want overwritten by a resource, you can add them to the `PROTECTED_FILES_BY_RESOURCE` setting. Include the resource ID and files you want to protect. e.g.,

```toml
[LIVE.PROTECTED_FILES_BY_RESOURCE]
1974 = ["CharSelect.cfg", "Zoned.cfg", "MQ2Map.ini", "MQ2MoveUtils.ini"]
153 = ["citymist.txt", "innothule.txt", "oasis.txt"]
navmesh = ["befallen.navmesh", "innothuleb.navmesh"]
```

### Custom category directories

If you share `lua`, `macros`, or `plugins` directories across multiple MQ environments, you can override where an entire category is installed. Add a `CATEGORY_PATHS` section to your `settings.local.toml`:

```toml
[DEFAULT.CATEGORY_PATHS]
lua = 'D:\\shared\\lua'
macros = 'D:\\shared\\macros'
```

Absolute paths are used as-is. Relative paths are joined to `DOWNLOAD_FOLDER`. You can set this globally in `[DEFAULT]` or per-environment (`[LIVE.CATEGORY_PATHS]`, `[TEST.CATEGORY_PATHS]`, etc.).

## Tinkerers

If you self-compile MacroQuest or use a discord friend's copy, you can still keep your scripts and plugins in sync with redfetch by opting out of Very Vanilla:

```powershell
redfetch.exe config SPECIAL_RESOURCES.1974.opt_in false --server LIVE
redfetch.exe config SPECIAL_RESOURCES.60.opt_in false --server EMU
redfetch.exe config SPECIAL_RESOURCES.2218.opt_in false --server TEST
```

Then assign the *Very Vanilla MQ* path to your self-compiled MacroQuest.

### Custom post-update launch

redfetch can launch extra programs after an update completes. Aside from the normal UI toggles, you can add `custom` to `POST_UPDATE_LAUNCH.targets` in `settings.local.toml`, then set `command` to whatever redfetch should run:

```toml
[LIVE.POST_UPDATE_LAUNCH]
targets = ["custom"]
command = ['C:\Tools\AfterRedfetch\after-update.exe', '--server', 'LIVE']
```

You can also combine it with the built-in post-update launches. For example, to start EQBCS and MySEQ and run your own Python script:

```toml
[LIVE.POST_UPDATE_LAUNCH]
targets = ["myseq", "custom", "eqbcs"]
command = ["C:\\Users\\Public\\Python\\python.exe", "C:\\Users\\Public\\redfetch\\after_update.py"]
```

You can set these per-server, e.g. `[TEST.POST_UPDATE_LAUNCH]`, or global `[DEFAULT.POST_UPDATE_LAUNCH]`.

![Watchers on RedGuides](https://www.redguides.com/community/resources/redfetch.3177/watchers-sparkline?months=12&w=500&h=180)

## Contributing

I'd love help, conceptually and technically. I'm not a developer and this is my first big python script. 

> [!NOTE]
> This project is built with LLM assistance.

To set up a [development environment](https://hatch.pypa.io/latest/environment/),

```bash
git clone https://github.com/RedGuides/redfetch
cd redfetch
pip install hatch
hatch env create dev
hatch shell dev
```
You can then run your dev version with,

`redfetch`

Or if the issue is ui-specific, run the [terminal UI in debug mode](https://textual.textualize.io/guide/devtools/#live-editing),

`textual run --dev .\src\redfetch\main.py`

When you're done, type `exit` to leave the shell.
```
Say you have a paragraph that
is formatted for a specific
length, so it has new line
characters without a space at
the end, like this text ...
```