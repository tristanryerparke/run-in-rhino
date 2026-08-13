# Rhino plugin debug lifecycle on macOS with VS Code

## What this is

This explains the normal **edit → build → launch Rhino under debugger → hit breakpoints → stop → rebuild** loop for Rhino plugin development on **macOS** using **VS Code**.

## Big picture

When you debug a Rhino plugin from VS Code on Mac, VS Code launches the **real Rhino app**:

```text
/Applications/Rhino 8.app/Contents/MacOS/Rhinoceros
```

So this is not a fake host or a special dev runtime.

That means:

- Rhino licensing is the normal Rhino licensing flow.
- Rhino preferences and normal plugin loading rules still apply.
- Your plugin code runs inside Rhino.
- Breakpoints hit when your plugin assembly is actually loaded and executed.

## Debug lifecycle

### 1. Edit code

Change your C# plugin code in VS Code.

### 2. Build

Your project needs to compile before a useful debug session can happen.

In template-generated setups, VS Code tasks usually build first.

### 3. Launch Rhino under debugger

Press **F5** in VS Code.

VS Code starts Rhino and attaches the Rhino debugger flow.

### 4. Rhino starts normally

Rhino opens like normal.

On first launch, or if Rhino is not already licensed/signed in, you may get the normal Rhino licensing/sign-in prompts.

### 5. Plugin assembly loads

This is the important part:

- Rhino does **not** necessarily load your plugin assembly the instant the app opens.
- Often the plugin gets loaded when Rhino needs it, e.g. when you run one of its commands.

Because of that, breakpoints may appear as **hollow/unbound** at first.

That is normal.

### 6. Run your plugin command

Once you trigger your plugin code, Rhino loads the assembly and your breakpoints become active.

### 7. Hit breakpoints and inspect state

Now you can:

- step over / into / out
- inspect locals
- inspect call stack
- continue execution

### 8. Stop debugging

When you stop the session, Rhino is no longer under the debugger.

### 9. Rebuild and relaunch

If you changed plugin code, the common loop is still:

- stop
- rebuild
- relaunch Rhino

## Important caveat: this is not magic hot reload

Using VS Code makes launching Rhino much easier, but it does **not** remove the normal loaded-DLL problem.

Once Rhino has loaded your plugin assembly, code changes usually mean:

1. stop debugging
2. quit Rhino if needed
3. rebuild
4. launch again

So the win is: **no manual launch/attach ceremony**.

## How licensing works

Rhino launched by VS Code is still just Rhino.

So licensing works exactly as usual:

- same Rhino license
- same sign-in / Zoo / Cloud Zoo / standalone behavior
- no separate “plugin developer” license mode

Good mental model:

> F5 is basically “start Rhino normally, but under a debugger.”

## Recommended setup path

## Option A: easiest path

Create the project from Rhino’s current templates and let the template give you the VS Code debug setup.

Typical bootstrap:

```bash
dotnet new install Rhino.Templates
mkdir MyPlugin
cd MyPlugin
dotnet new rhino --version 8 -sample
```

Then open the folder in VS Code and press **F5**.

## Option B: wire an existing plugin manually

For an existing project, create a `.vscode/launch.json`.

## VS Code extension

McNeel has a VS Code Rhino debugger extension with a config shape like this:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Launch Rhino 8",
      "type": "rhino",
      "request": "launch",
      "runtimeExecutable": "/Applications/Rhino 8.app/Contents/MacOS/Rhinoceros",
      "passDebugOptionsViaEnvironmentVariable": true,
      "env": {
        "RHINO_PLUGIN_PATH": "${workspaceFolder}/bin/Debug/net7.0/MyPlugin.rhp"
      }
    }
  ]
}
```

If you also need Grasshopper plugin loading, the same extension README shows:

```json
"env": {
  "RHINO_PLUGIN_PATH": "${workspaceFolder}/Path/To/MyPlugin.rhp",
  "GRASSHOPPER_PLUGINS": "${workspaceFolder}/Path/To/MyGHPlugin.gha"
}
```

## Notes on that config

- `runtimeExecutable` is the Rhino app binary on macOS.
- `type: "rhino"` is for McNeel’s Rhino debug extension.
- `RHINO_PLUGIN_PATH` is the key trick for making Rhino load your development plugin build.
- `passDebugOptionsViaEnvironmentVariable` is part of the Rhino debug extension’s launch mechanism.

## Minimal tasks.json

If you want VS Code to build before launch, a minimal task can look like this:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "build",
      "type": "process",
      "command": "dotnet",
      "args": ["build"],
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "problemMatcher": "$msCompile"
    }
  ]
}
```

And then in `launch.json`:

```json
"preLaunchTask": "build"
```

## Suggested practical setup for an existing plugin

1. Confirm your plugin builds with:

```bash
dotnet build
```

2. Find the built `.rhp` path.
3. Add `.vscode/launch.json` pointing Rhino at:

```text
/Applications/Rhino 8.app/Contents/MacOS/Rhinoceros
```

4. Set `RHINO_PLUGIN_PATH` to your built plugin.
5. Press **F5**.
6. In Rhino, run your command.

## What to expect on first breakpoint

If a breakpoint is hollow before your command runs, that usually just means:

- Rhino is launched
- debugger is attached
- your plugin assembly has not been loaded yet

Run your plugin command once. That usually binds the breakpoint.

## Common failure modes

### Rhino launches but breakpoints never hit

Usually one of:

- wrong plugin output path in `RHINO_PLUGIN_PATH`
- plugin never actually loaded
- command you ran is from a different installed copy of the plugin
- symbols/debug build mismatch

### Rhino opens but not your dev build

You likely have another installed copy of the plugin being loaded instead.

Use the development output path explicitly.

### Licensing prompt appears

Normal. Rhino is just starting normally.

### Code changed but behavior did not

Classic loaded assembly problem. Stop, rebuild, relaunch.

## Recommended workflow

The boring workflow is the good workflow:

1. edit
2. build
3. F5
4. run plugin command
5. debug
6. stop
7. repeat

## Bottom line

- VS Code on Mac can launch Rhino directly for plugin debugging.
- Rhino still behaves like the real app: normal licensing, normal plugin loading.
- Breakpoints bind when your plugin assembly is loaded.
- You still usually need stop/rebuild/relaunch after code changes.
