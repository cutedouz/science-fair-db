# 科展資料庫

搜尋全國中小學科展與臺灣國際科展歷屆作品（1974–2025，共 14,077 件）、查看相似研究、查證研究方向，並把勾選的作品匯出成「研究包」給 Gemini Notebook 等 AI 工具分析。

網站是純靜態頁面，放在 `site/`，由 GitHub Actions 發布到 GitHub Pages。

## 資料來源與原則

- 作品資料來自[國立臺灣科學教育館](https://www.ntsec.edu.tw/science/list.aspx)，依其[政府網站資料開放宣告](https://www.ntsec.edu.tw/article/detail.aspx?a=13931)使用。本站並非科教館官方網站。
- 網站不收錄作者姓名；作者資訊請見各作品的科教館原始頁面。
- 「領域」「學習階段」為本站整理，原始欄位一律保留顯示。

## 每年更新資料

原始資料、PDF 與 Excel 不放在這個 repo（見 `.gitignore`），需在本機執行：

```bash
python3 scraper/scan.py 1 30000                 # 1. 抓科教館作品頁（輸出 data/raw/scan.jsonl）
python3 scraper/heads.py                         # 2. 讀 PDF 檔名取得作品編號（data/raw/filenames.json）
python3 pipeline/clean.py                        # 3. 整理成 data/works.json
python3 pipeline/learn_font_fix.py                # 4. （第 55 屆字型編碼錯誤）比對網站摘要學出錯字對照表
python3 pipeline/extract_fulltext.py             #    從 PDF原始檔 抽研究內容節錄（可加 --editions 54,55）
python3 pipeline/finish_fulltext.py              #    補跑失敗的檔案並產生報告
python3 pipeline/redact_fulltext.py              #    產生網站版節錄：遮蔽作者姓名、移除金鑰（必做）
python3 pipeline/build_site_data.py --similar    # 5. 產生網站資料（--similar 重算相似作品）
python3 pipeline/build_xlsx.py                   # 6. 產生自用 Excel（含作者，勿公開）
git add site && git commit -m "更新資料" && git push
```
