# 用户 C 盘清理评审（只读）— Downloads / Desktop 分类

生成时间: 2026-08-31 15:14:59
**模式: 只读审计 — 未移动/删除/重命名任何用户文件。所有分类仅作建议，最终动作需用户确认。**

## 分类口径
- `MEDIA_TO_Z`: 视频/音频/图片大文件 → Z 盘素材候选（需用户确认后再迁）
- `INSTALLER_DELETE`: 安装包/更新程序 → 删除候选
- `ARCHIVE_REVIEW`: 压缩包/镜像 → 解压或删除候选
- `PROJECT_TO_E`: 开发项目目录 → E 盘候选
- `DUPLICATE`: 同名同大小重复 → 保留一份候选
- `KEEP`: 文档/快捷方式/配置 → 保留
- `UNKNOWN_KEEP`: 无法可靠分类 → **一律保留**（UNKNOWN 不是 FALSE）

## DOWNLOADS — 21.33 GB / 31470 文件

| 类别 | 大小(GB) | 文件数 |
|---|---|---|
| INSTALLER_DELETE | 8.42 | 62 |
| PROJECT_TO_E | 8.18 | 27878 |
| DUPLICATE | 4.24 | 3104 |
| MEDIA_TO_Z | 0.29 | 304 |
| ARCHIVE_REVIEW | 0.18 | 7 |
| UNKNOWN_KEEP | 0.02 | 86 |
| KEEP | 0.0 | 29 |

### 项目目录候选 (PROJECT_TO_E)

- `cc-switch-main\cc-switch-main`
- `cc-switch-main\cc-switch-main\src-tauri`

### 大文件 Top（≥50MB，按大小）

| 大小(GB) | 路径 | 类别 |
|---|---|---|
| 1.77 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\cc_switch_lib.lib` | PROJECT_TO_E |
| 1.77 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\deps\cc_switch_lib.lib` | DUPLICATE |
| 1.3 | `OllamaSetup.exe` | INSTALLER_DELETE |
| 0.93 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\libcc_switch_lib.rlib` | PROJECT_TO_E |
| 0.93 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\deps\libcc_switch_lib.rlib` | DUPLICATE |
| 0.71 | `ChatGPT-x64.msix` | INSTALLER_DELETE |
| 0.37 | `BaiduNetdisk_7.44.7.1.exe` | INSTALLER_DELETE |
| 0.35 | `Feishu-win32_x64-7.69.9-signed.exe` | INSTALLER_DELETE |
| 0.33 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\cc_switch.pdb` | PROJECT_TO_E |
| 0.33 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\deps\cc_switch.pdb` | DUPLICATE |
| 0.31 | `OppoConnectSetUp_16.0.21_domestic_251202163134_ad0b86cf9.exe` | INSTALLER_DELETE |
| 0.31 | `Doubao_installer (1).exe` | INSTALLER_DELETE |
| 0.3 | `MCLauncher_1.14.0.36188.exe` | INSTALLER_DELETE |
| 0.26 | `WeChatSetup.exe` | INSTALLER_DELETE |
| 0.26 | `QQ_9.9.20_250626_x64_01.exe` | INSTALLER_DELETE |
| 0.24 | `千帆客服工作台_setup_1.2.6 (1).exe` | INSTALLER_DELETE |
| 0.24 | `千帆客服工作台_setup_1.2.6.exe` | INSTALLER_DELETE |
| 0.23 | `WPS_Setup_18608.exe` | INSTALLER_DELETE |
| 0.23 | `i4Tools8_v8.37_Setup_x64 (1).exe` | INSTALLER_DELETE |
| 0.23 | `i4Tools8_v8.37_Setup_x64.exe` | INSTALLER_DELETE |
| 0.23 | `i4Tools8_v8.36_Setup_x64.exe` | INSTALLER_DELETE |
| 0.23 | `i4Tools8_v8.32_Setup_x64 (1).exe` | INSTALLER_DELETE |
| 0.23 | `i4Tools8_v8.32_Setup_x64.exe` | INSTALLER_DELETE |
| 0.22 | `Doubao_installer.exe` | INSTALLER_DELETE |
| 0.21 | `qianniu_(9.72.00N)_NK_64.exe` | INSTALLER_DELETE |
| 0.2 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\incremental\cc_switch_lib-3fdawu3o9cq2b\s-hj7zeapdbo-09ty4cy-3sa2i6qdl657kke45vthsu5ne\dep-graph.bin` | PROJECT_TO_E |
| 0.2 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\incremental\cc_switch_lib-3fdawu3o9cq2b\s-hj7wy26bew-0tqqm1c-3sa2i6qdl657kke45vthsu5ne\dep-graph.bin` | PROJECT_TO_E |
| 0.19 | `EpicInstaller-17.2.0-ded2ff17bdd84b8f9fff41a1545987dc.msi` | INSTALLER_DELETE |
| 0.17 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\cc_switch_lib.pdb` | PROJECT_TO_E |
| 0.17 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\deps\cc_switch_lib.pdb` | DUPLICATE |
| 0.16 | `sogou_pinyin_15.4c.exe` | INSTALLER_DELETE |
| 0.15 | `Xmind-for-Windows-x64bit-25.01.01061-202501070746.exe` | INSTALLER_DELETE |
| 0.14 | `NeteaseCloudMusic_Music_official_3.0.5.203184_64.exe` | INSTALLER_DELETE |
| 0.14 | `ToDesk_4.9.6.0.exe` | INSTALLER_DELETE |
| 0.13 | `SodaMusic-v2.9.1-official-win32_x64.exe` | INSTALLER_DELETE |
| 0.13 | `pot_x306_installer.exe` | INSTALLER_DELETE |
| 0.12 | `LeiGodSetup.10.1.9.9.exe` | INSTALLER_DELETE |
| 0.12 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\deps\libwindows-8bacceea3a6e124e.rlib` | PROJECT_TO_E |
| 0.12 | `clash.verge_64.0604.zip` | ARCHIVE_REVIEW |
| 0.11 | `cc-switch-main\cc-switch-main\src-tauri\target\debug\incremental\cc_switch_lib-3fdawu3o9cq2b\s-hj7wy26bew-0tqqm1c-3sa2i6qdl657kke45vthsu5ne\query-cache.bin` | PROJECT_TO_E |

### 重复簇（同名同大小）

- `license` (0.00 GB): cc-switch-main\cc-switch-main\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\has-tostringtag@1.0.2\node_modules\has-tostringtag\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\supports-preserve-symlinks-flag@1.0.0\node_modules\supports-preserve-symlinks-flag\LICENSE
- `license` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@adobe+css-tools@4.4.4\node_modules\@adobe\css-tools\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\is-binary-path@2.1.0\node_modules\is-binary-path\license
- `license` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@alloc+quick-lru@5.2.0\node_modules\@alloc\quick-lru\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\ansi-regex@5.0.1\node_modules\ansi-regex\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\ansi-styles@4.3.0\node_modules\ansi-styles\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\ansi-styles@5.2.0\node_modules\ansi-styles\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\chalk@4.1.1\node_modules\chalk\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\check-error@2.1.1\node_modules\check-error\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\deep-eql@5.0.2\node_modules\deep-eql\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\has-flag@4.0.0\node_modules\has-flag\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\indent-string@4.0.0\node_modules\indent-string\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\is-fullwidth-code-point@3.0.0\node_modules\is-fullwidth-code-point\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\parse5@7.3.0\node_modules\parse5\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\redent@3.0.0\node_modules\redent\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\string-width@4.2.3\node_modules\string-width\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\strip-ansi@6.0.1\node_modules\strip-ansi\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\strip-indent@3.0.0\node_modules\strip-indent\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\supports-color@7.2.0\node_modules\supports-color\license ; cc-switch-main\cc-switch-main\node_modules\.pnpm\wrap-ansi@6.2.0\node_modules\wrap-ansi\license
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@alloc+quick-lru@5.2.0\node_modules\@alloc\quick-lru\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\rettime@0.7.0\node_modules\rettime\package.json
- `readme.md` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@alloc+quick-lru@5.2.0\node_modules\@alloc\quick-lru\readme.md ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@csstools+css-calc@2.1.4_@c_e8d5cb57048a11d39451107410ea18b6\node_modules\@csstools\css-calc\README.md
- `license` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@asamuzakjp+css-color@3.2.0\node_modules\@asamuzakjp\css-color\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\object-hash@3.0.0\node_modules\object-hash\LICENSE
- `license` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+code-frame@7.27.1\node_modules\@babel\code-frame\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+compat-data@7.28.0\node_modules\@babel\compat-data\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+core@7.28.0\node_modules\@babel\core\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+generator@7.28.0\node_modules\@babel\generator\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-compilation-targets@7.27.2\node_modules\@babel\helper-compilation-targets\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-globals@7.28.0\node_modules\@babel\helper-globals\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-module-imports@7.27.1\node_modules\@babel\helper-module-imports\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-module-transforms@7.27.3_@babel+core@7.28.0\node_modules\@babel\helper-module-transforms\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-plugin-utils@7.27.1\node_modules\@babel\helper-plugin-utils\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-string-parser@7.27.1\node_modules\@babel\helper-string-parser\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-option@7.27.1\node_modules\@babel\helper-validator-option\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+plugin-transform-rea_14f443ec5a1a57930c5dbef59833477c\node_modules\@babel\plugin-transform-react-jsx-source\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+plugin-transform-rea_37cb12b06dade4cd1811367ea4497574\node_modules\@babel\plugin-transform-react-jsx-self\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+runtime@7.28.4\node_modules\@babel\runtime\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+template@7.27.2\node_modules\@babel\template\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+traverse@7.28.0\node_modules\@babel\traverse\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+types@7.28.2\node_modules\@babel\types\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+types@7.28.5\node_modules\@babel\types\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\sucrase@3.35.1\node_modules\sucrase\LICENSE
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+compat-data@7.28.0\node_modules\@babel\compat-data\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\clsx@2.1.1\node_modules\clsx\package.json
- `parser.cmd` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+core@7.28.0\node_modules\@babel\core\node_modules\.bin\parser.CMD ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+generator@7.28.0\node_modules\@babel\generator\node_modules\.bin\parser.CMD ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+template@7.27.2\node_modules\@babel\template\node_modules\.bin\parser.CMD ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+traverse@7.28.0\node_modules\@babel\traverse\node_modules\.bin\parser.CMD
- `parser.ps1` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+core@7.28.0\node_modules\@babel\core\node_modules\.bin\parser.ps1 ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+generator@7.28.0\node_modules\@babel\generator\node_modules\.bin\parser.ps1 ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+template@7.27.2\node_modules\@babel\template\node_modules\.bin\parser.ps1 ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+traverse@7.28.0\node_modules\@babel\traverse\node_modules\.bin\parser.ps1
- `semver.cmd` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+core@7.28.0\node_modules\@babel\core\node_modules\.bin\semver.CMD ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-compilation-targets@7.27.2\node_modules\@babel\helper-compilation-targets\node_modules\.bin\semver.CMD
- `semver.ps1` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+core@7.28.0\node_modules\@babel\core\node_modules\.bin\semver.ps1 ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-compilation-targets@7.27.2\node_modules\@babel\helper-compilation-targets\node_modules\.bin\semver.ps1
- `index.js.map` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+generator@7.28.0\node_modules\@babel\generator\lib\node\index.js.map ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@radix-ui+react-slot@1.2.3_@types+react@18.3.23_react@18.3.1\node_modules\@radix-ui\react-slot\dist\index.js.map
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-module-imports@7.27.1\node_modules\@babel\helper-module-imports\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\redent@3.0.0\node_modules\redent\package.json
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\is-fullwidth-code-point@3.0.0\node_modules\is-fullwidth-code-point\package.json
- `readme.md` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\README.md ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\README.md
- `index.js` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\lib\index.js ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\lib\index.js
- `index.js.map` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\lib\index.js.map ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\lib\index.js.map
- `keyword.js` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\lib\keyword.js ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\lib\keyword.js
- `keyword.js.map` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.27.1\node_modules\@babel\helper-validator-identifier\lib\keyword.js.map ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-identifier@7.28.5\node_modules\@babel\helper-validator-identifier\lib\keyword.js.map
- `readme.md` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-option@7.27.1\node_modules\@babel\helper-validator-option\README.md ; cc-switch-main\cc-switch-main\node_modules\.pnpm\scheduler@0.23.2\node_modules\scheduler\README.md
- `index.js` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+helper-validator-option@7.27.1\node_modules\@babel\helper-validator-option\lib\index.js ; cc-switch-main\cc-switch-main\node_modules\.pnpm\nanoid@3.3.11\node_modules\nanoid\non-secure\index.js
- `changelog.md` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.0\node_modules\@babel\parser\CHANGELOG.md ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.5\node_modules\@babel\parser\CHANGELOG.md
- `license` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.0\node_modules\@babel\parser\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.5\node_modules\@babel\parser\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\pretty-format@27.5.1\node_modules\pretty-format\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\react-dom@18.3.1_react@18.3.1\node_modules\react-dom\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\react-is@17.0.2\node_modules\react-is\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\react@18.3.1\node_modules\react\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\scheduler@0.23.2\node_modules\scheduler\LICENSE ; cc-switch-main\cc-switch-main\node_modules\.pnpm\xmlchars@2.2.0\node_modules\xmlchars\LICENSE
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.0\node_modules\@babel\parser\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.5\node_modules\@babel\parser\package.json
- `readme.md` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.0\node_modules\@babel\parser\README.md ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.5\node_modules\@babel\parser\README.md
- `babel-parser.js` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.0\node_modules\@babel\parser\bin\babel-parser.js ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+parser@7.28.5\node_modules\@babel\parser\bin\babel-parser.js
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+runtime@7.28.4\node_modules\@babel\runtime\helpers\esm\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@testing-library+user-event_1ca100c7362ccf0b1358603d616c282d\node_modules\@testing-library\user-event\dist\esm\package.json
- `package.json` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+template@7.27.2\node_modules\@babel\template\package.json ; cc-switch-main\cc-switch-main\node_modules\.pnpm\crelt@1.0.6\node_modules\crelt\package.json
- `parser` (0.00 GB): cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+template@7.27.2\node_modules\@babel\template\node_modules\.bin\parser ; cc-switch-main\cc-switch-main\node_modules\.pnpm\@babel+traverse@7.28.0\node_modules\@babel\traverse\node_modules\.bin\parser

---

## DESKTOP — 7.5 GB / 360 文件

| 类别 | 大小(GB) | 文件数 |
|---|---|---|
| MEDIA_TO_Z | 7.33 | 290 |
| KEEP | 0.13 | 67 |
| INSTALLER_DELETE | 0.03 | 1 |
| UNKNOWN_KEEP | 0.0 | 1 |
| ARCHIVE_REVIEW | 0.0 | 1 |

### 大文件 Top（≥50MB，按大小）

| 大小(GB) | 路径 | 类别 |
|---|---|---|
| 0.54 | `协助运营剪辑文件夹\12.21\12月21日 (6).mp4` | MEDIA_TO_Z |
| 0.52 | `协助运营剪辑文件夹\12.22\12月22日 (4).mp4` | MEDIA_TO_Z |
| 0.45 | `协助运营剪辑文件夹\12.22\12月22日 (2).mp4` | MEDIA_TO_Z |
| 0.45 | `协助运营剪辑文件夹\12.27\12月27日 (2).mp4` | MEDIA_TO_Z |
| 0.43 | `协助运营剪辑文件夹\12.20\12月20日已剪  (2).mp4` | MEDIA_TO_Z |
| 0.41 | `协助运营剪辑文件夹\12.21\12月21日 (12).mp4` | MEDIA_TO_Z |
| 0.4 | `协助运营剪辑文件夹\12.22\12月22日 (1).mp4` | MEDIA_TO_Z |
| 0.39 | `协助运营剪辑文件夹\12.21\12月22日 (1).mp4` | MEDIA_TO_Z |
| 0.34 | `协助运营剪辑文件夹\12.21\12月21日 (13).mp4` | MEDIA_TO_Z |
| 0.32 | `协助运营剪辑文件夹\12.21\12月21日 (11).mp4` | MEDIA_TO_Z |
| 0.32 | `协助运营剪辑文件夹\12月27日.mp4` | MEDIA_TO_Z |
| 0.31 | `协助运营剪辑文件夹\12.21\12月21日 (9).mp4` | MEDIA_TO_Z |
| 0.27 | `协助运营剪辑文件夹\12.27\12月27日 (1).mp4` | MEDIA_TO_Z |
| 0.24 | `协助运营剪辑文件夹\12.21\12月21日 (8).mp4` | MEDIA_TO_Z |
| 0.21 | `协助运营剪辑文件夹\12.20\12月20日已剪 (3).mp4` | MEDIA_TO_Z |
| 0.19 | `协助运营剪辑文件夹\12.22\12月22日 (6).mp4` | MEDIA_TO_Z |
| 0.19 | `协助运营剪辑文件夹\12.20\12月20日 (5).mp4` | MEDIA_TO_Z |
| 0.14 | `协助运营剪辑文件夹\12.21\12月21日 (7).mp4` | MEDIA_TO_Z |
| 0.11 | `协助运营剪辑文件夹\12.21\12月21日 (5).mp4` | MEDIA_TO_Z |
| 0.1 | `协助运营剪辑文件夹\12.20\12月20日已剪    （1）.mp4` | MEDIA_TO_Z |
| 0.08 | `12月24日 (4)\12月24日 (4)-1.mp4` | MEDIA_TO_Z |
| 0.08 | `协助运营剪辑文件夹\12.22\12月22日 (5).mp4` | MEDIA_TO_Z |
| 0.06 | `bgm\雷霆 - 雷霆.wav（翻自 Zxxy）.mp3` | MEDIA_TO_Z |
| 0.05 | `【B008】【KUBON坤宝岛台工厂】【0000.00.00起】爆款内容记录表.xlsx` | KEEP |

---

## 决策说明
- 本评审不自动执行任何动作；请在逐项确认后再决定迁移/删除。
- 迁移候选在动作前需先确认目标盘空间与用途。
- 任何无法确认类别的文件按 KEEP 处理。