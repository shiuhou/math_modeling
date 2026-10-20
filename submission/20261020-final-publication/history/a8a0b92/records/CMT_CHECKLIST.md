# Beichen Ji 的 CMT 提交清單

依據：本次官方 Problem B 第 3 頁，以及本次提供的 Registration and Submission Guidelines 第 1–8 頁（第 6–8 頁上傳畫面已核對）。文件 SHA-256 及頁碼保存在相鄰 submission_manifest.json。此清單不是登入或上傳回執。

截止：**2026 年 10 月 20 日 23:59，北京時間（UTC+8）**。提交時再核對官方／CMT 顯示的時區和截止。不要引用相對日期。

1. 先完成 TEAM_REVIEW.md 對指定 hash 的簽核。現階段檔案仍為 REVIEW_ONLY；確認後只使用 UPLOAD/ 中的兩份同 hash 檔案。
2. 由已確認上傳者 Beichen Ji 使用原有隊長 HKUST(GZ) 電郵帳號，在 `https://cmt3.research.microsoft.com/HKUSTGZMCM2026` 開啟既有 **Senior Track** 報名紀錄，角色為 Author。隊名為 falcons；核對四位英文姓名及順序。指南要求的電郵和學號只在原 CMT 紀錄中核對，不放入 Git 或程式 ZIP。不新建隊伍、不自行移除成員、不修改報名資料。指南畫面中的 Junior Track 是示例，不是本隊目標 Track。
3. 選 **Edit Submission**，上傳 `Problem_B_Report.pdf`；由隊長親自確認表單所需聲明，再按 **Save changes**。
4. 回到同一報名紀錄，選 **Upload Supplementary Material**，上傳 `Problem_B_Code.zip`，另按 **Save**。主報告與程式 ZIP 分開儲存。兩份檔案都低於保守的 50,000,000-byte 上限。
5. 重新開啟紀錄，確認兩份檔案均存在。若可下載，下載兩份檔案，核對名稱、大小和 SHA-256 與 submission_manifest.json 一致；Linux 可用 `sha256sum Problem_B_Report.pdf Problem_B_Code.zip`。若系統改動下載檔名，仍核對內容 hash。
6. 保存最後提交畫面／確認紀錄，確認使用這次簽核的檔案，而非舊 R1/R2。若 CMT 顯示未儲存或錯誤，依真實狀態處理，不記成成功。
7. 檔案及團隊簽核齊備後即由隊長提交；不等待 Git PR 合併、tag 或非必要大型帳本共享。

Codex 未登入、未代填身份、未勾聲明、未上傳，也未收到提交回執。ACTUALLY_SUBMITTED 保持 NOT_RUN，直到隊長提供實際結果。
