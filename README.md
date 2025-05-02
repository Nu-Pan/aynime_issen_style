# えぃにめ一閃流奥義 ――スクショ―― `(aynime_issen_style)`

> **ワンキー一閃、選んだウィンドウだけを瞬時にキャプチャしてクリップボードへ。**  
> Discord や Slack に <kbd>Ctrl+V</kbd> で即ペースト。GUI もホットキーも軽快に動く、  
> Python 製 “超” ミニマル・スクショツールです。

---

## ✨ 主な特徴
| 機能 | 説明 |
|------|------|
| 🎯 **ピンポイント撮影** | GUI で対象ウィンドウを選択 → そのウィンドウだけをキャプチャ |
| ⚡ **グローバルホットキー** | デフォルト <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd>（変更可）でいつでも撮影 |
| 🖼 **プレビュー兼ボタン** | クリックしてもキャプチャ。撮った画像は即座にプレビュー表示 |
| 📋 **クリップボード直送 (CF\_DIB)** | 無圧縮 BMP 相当でコピー → Discord などにそのまま貼れる |
| 🔔 **オンスクリーン通知** | コピー完了を画面中央にフェード表示（カスタム色・日本語フォント対応） |
| 🛠 **Python だけで完結ビルド** | `build.py` 1発で PyInstaller ビルド & ZIP 圧縮 |

---

## 🖥️ スクリーンショット
<!-- ここに imgs フォルダを作って GUI の画像を貼れば README がさらに映えます -->
> 選択・プレビュー・コピー通知が 1 画面に収まるミニマル UI

---

## 🚀 クイックスタート

### 1. 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 2. 実行
```bash
python main.py
```
1. **Window** タブで対象ウィンドウをクリック  
2. **Capture** タブでプレビュー領域をクリック *または* <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd>  
3. 「クリップボードにコピーしました」通知が出たら、Discord などに <kbd>Ctrl+V</kbd>

---

## 🏗️ ビルド (Windows)

```bash
python build.py      # dist/AynimeCapture.exe を生成し、release/ に ZIP を作成
```

- `main.spec` にアイコンやリソースを定義済み  
- 出力された `AynimeCapture_yyyyMMdd.zip` を配布するだけで OK

---

## ⌨️ ホットキー変更

```python
# capture_frame.py 付近
keyboard.add_hotkey("ctrl+alt+p", lambda: self.on_capture(None))
```

任意のキーコンビネーションに変更し、再ビルドしてください。

---

## 📁 ディレクトリ構成（抜粋）

```
.
├─ main.py                # エントリポイント
├─ window_selection_frame.py
├─ capture_frame.py
├─ build.py               # PyInstaller + ZIP 自動化スクリプト
├─ main.spec              # PyInstaller 設定（Git 管理）
└─ requirements.txt
```

---

## 🪪 License

MIT License — © 2025 Nu‑Pan  
詳細は `LICENSE` ファイルをご覧ください。
