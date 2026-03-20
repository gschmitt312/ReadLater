# ReadLater Browser Extension

One-click saving to your ReadLater server.

## Install (Chrome / Edge / Brave)

1. Open `chrome://extensions`
2. Enable **Developer mode** (toggle, top-right)
3. Click **Load unpacked**
4. Select the `extension/` folder from this repo

## Install (Firefox)

1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on**
3. Select `extension/manifest.json`

> Note: Firefox requires a persistent install via `about:addons` for non-temporary use;
> sign your extension or use Firefox Developer Edition.

## Configuration

By default the extension talks to `http://localhost:8000`.
Click the ⚙ gear icon in the popup to change the server URL.

## Usage

1. Navigate to any webpage, tweet, or YouTube video
2. Click the ReadLater toolbar icon
3. Optionally add tags, then click **Save to ReadLater**
