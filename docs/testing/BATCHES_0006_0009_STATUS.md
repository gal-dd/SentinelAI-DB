# מנות 0006–0009 — סקירת דוחות ושלמות מבנית

תאריך: 2026-11-19. ענף העדכון: `poc/defense-focused-v2`, בסיס `73dc31dd7786de4ca25cfc2635d9e21af17fa7df`. ענף הטיוטות שנקרא בלבד: `producer/chat-defense-v2`, בסיס `287d2724f10b2acefcab262d8d7cd3d185072317`. שני עצי העבודה היו נקיים בתחילת הבדיקה. מסמכי הניהול נשמרים בענף הייצור בלבד.

ההיקף: קריאת דוחות קיימים, בדיקת קבצים מבנית וריכוז חסמים. לא שונו תוכן, טיוטות, דוחות המקור, מכסות, קוד או מדיניות. מנות 0001–0005 לא נפתחו לבדיקה. לפי `progress.json` בלבד: 2,500 רשומות שפורסמו, מנה אחרונה 0005, מזהה הבא 2501. אין אישור לפרסום מנות נוספות.

## מקורות והכרעה בין סטטוסים

- ייצור: `drafts/work/batch-0006/` — מועמדים, `status.json`,‏ `qa-report.json`,‏ `blind-review.jsonl`.
- טיוטות: `drafts/chat/batch-0006/` — מועמדים, סטטוס ודוח QA; במנות 0007–0009 גם `diversity-audit.json` ו־`remediation-queue.json`.
- מקור טיוטות קבוע לקריאה מרחוק: [עץ הטיוטות ב־SHA שנבדק](https://github.com/gal-dd/SentinelAI-DB/tree/287d2724f10b2acefcab262d8d7cd3d185072317/drafts/chat).

| מנה/עותק | מועמדים בפועל | סטטוס קובע | חסם מתועד |
|---|---:|---|---|
| 0006 Chat | 500 | `complete_draft_pending_independent_review` | מוכנה לקליטת Work בלבד; אינה מוכנה לייצור |
| 0006 Work | 500 | `initial_repairs_in_progress` | ביקורת ראשונית של 25 בלבד; 19 רשומות שונות מהמקור; ביקורת התיקונים טרם הושלמה |
| 0007 | 500 | `editorial_remediation_required` | 132 קבוצות חזרה; 243 רשומות מושפעות (48.6%) |
| 0008 | 500 | `editorial_remediation_required` | 151 קבוצות חזרה; 226 רשומות מושפעות (45.2%) |
| 0009 | 500 | `editorial_remediation_required` | 173 קבוצות חזרה; 267 רשומות מושפעות (53.4%) |

עותקי Chat ו־Work של 0006 הם גרסאות שונות של אותה מנה, ולא שתי מנות לפרסום. כל דגלי המוכנות לייצור והקצאת מזהי הייצור שנמצאו שליליים; אין שדה מזהה ייצור ברשומות המועמדים. במנות 0007–0009 דוח הגיוון המאוחר מבטל מסקנות מוכנות טכנית קודמות, ודגל `ready_for_work_intake` הוא false. אפס זוגות Jaccard אינם סותרים קיום משפטים ופסקאות שחוזרים בתוך מסמכים שונים.

## בדיקות חדשות שבוצעו מקומית

בדיקה ייעודית בספרייה התקנית, Windows ו־Python 3.13.14 מהסביבה הקיימת `.venv-dev`, ללא התקנות או מודל. קוד הבדיקה והתוצאה המפורטים נשמרו מקומית, מחוץ ל־Git, תחת `.poc-local/batch-status-2026-11-19/`. לאחר בירור פערי hashes בהרצה הראשונית, הבדיקה הורצה שוב עם השוואת בתי Git כמפורט להלן.

| בדיקה | תוצאה |
|---|---|
| קיום וקריאת כל קובצי חמש תיקיות המנה | 22 קבצים: 16 JSON ו־6 JSONL; כל הקבצים נקראו כ־UTF-8 ללא BOM |
| JSON מחמיר | אין מפתחות כפולים או NaN/Infinity; אובייקטים תקינים; אין שורות JSONL ריקות |
| ספירת מועמדים | 500 בכל אחד מחמשת הקבצים; 2,500 שורות נבדקו, ובהן שני עותקים של 0006 |
| מבנה מועמדים | 13 שדות בכל שורה, טיפוסים, מחרוזות לא ריקות וללא רווחי קצה, מזהים, ערכי קטגוריה ורשימות תחומים משניים תקינים |
| ספירות מול דוחות | 125 מועמדים לכל תווית; 300 בתחום הטילי ו־50/50/50/25/25 ביתר התחומים, בכל עותק; התאמה לדוחות |
| התפלגות אורך מוצהר | בכל תווית ובכל עותק `[6,50,44,25]` לפי short/sentence/paragraph/long; תואמת לדוחות |
| הפניות קבצים בסטטוסים של Chat | קובצי המועמדים, QA והגיוון המופנים קיימים |
| ביקורת Work 0006 | 25 מיקומים ייחודיים ותקפים; 19 דגלי repaired תואמים למיקומים 7–25 ולהבדלים בפועל בין קובצי המועמדים |
| תורי 0007–0009 | מספרי הקבוצות והרשומות תואמים ל־QA ולדוחות הגיוון; מיקומים 1–500, מזהי קבוצות ייחודיים, repeat_count, איחוד רשומות, חברות בקבוצות ומטא־דאטה לכל רשומה בתור תואמים |
| הפניות top_groups בדוחות הגיוון | מיקומים וספירות מופעים עקביים מבנית |
| מקור Work 0006 | Git blob של מקור Chat תואם ל־`source_candidate_blob`; SHA-256 של שני קובצי המועמדים ב־Git תואם להצהרות Work |

לא נמצאו כשלים בבדיקה המבנית הסופית. זו אינה הרצת validator מלא של הפרויקט: לא חושבו מחדש אורכי הטקסטים, רישום התרחישים, רלוונטיות תחום, תוויות או חזרות תוכן. בתורי התיקון נבדקו המבנה וההפניות, ולא נכונות טקסט החזרה מול הטקסט המקורי.

## בדיקות קיימות — נקראו ולא הורצו מחדש

| מקור | ראיה מדווחת | מגבלה |
|---|---|---|
| QA Chat 0006–0009 | פענוח, ספירה, תרחישים ומטא־דאטה, עברית, אורכים וצורת מסמכים; אפס כפילויות מלאות ואפס זוגות Jaccard בסף 0.73 מול קבוצות הייחוס הרשומות | דוחות ה־Chat מבוססים על ייצור 0003/1,500 ועל טיוטות מקבילות, ולא על מצב הייצור הנוכחי |
| QA Work 0006, baseline של מקור Chat | schema ו־document_form עברו; אפס כפילויות מלאות; 57 קבוצות פסקאות חוזרות ב־91 רשומות; סריקת E5 מדווחת completed,‏ 3,365 זוגות סמנטיים ו־467 זוגות בסיכון גבוה; גם 31 זוגות לקסיקליים בפירוט | ה־baseline קודם ל־19 שינויי Work; אינו תוצאת E5 לעותק Work הנוכחי |
| QA Work 0006 לאחר תיקונים | אפס exact_duplicates ו־28 native_lexical_alerts; ייחוס מפורש לייצור 0005/2,500; 25 ביקורות ראשוניות ו־19 שינויים | independent_revised_review_pending הוא true; אין דוח E5 מעודכן לעותק המתוקן |
| diversity-audit ו־remediation-queue של 0007–0009 | חזרות משפטים/פסקאות והיקפי הפגיעה שבטבלה; חסימת קליטת Work וייצור | אינם ביקורת סמנטית או ביקורת תוויות/תחומים; לא חושבו מחדש כאן |
| followup_audit של 0009 | אפס בעיות מבנה, כפילויות וזוגות לקסיקליים מדווחים; 12 תיקוני התאמה דקדוקית | דוח הגיוון המאוחר מחייב תיקון עריכתי למרות תוצאות אלה |

בדיקות תשתית, E5 ומטמון מהסבבים הקודמים מתועדות ב־[TECHNICAL_STATUS.md](../../TECHNICAL_STATUS.md). הן אינן בדיקות איכות של המנות, ואין צורך לחזור על הקמה או תיקוני תוכנה במסגרת סקירה זו.

## סתירות, הבדלי גרסאות וחסמים שנותרו

1. **מכסות:** `label_length_quota: passed` ההיסטורי מתייחס לתכנון הישן. בפועל בכל העותקים `[6,50,44,25]` לכל תווית, ואילו המנה הבאה לפי `progress.json` דורשת `[7,50,43,25]`. אף עותק אינו תואם למכסת המנה הבאה כעת. אין להחיל מכסה זו אוטומטית על 0007–0009 העתידיות; יש לחשב מחדש במועד קליטה לאחר שינוי ההתקדמות.
2. **מקור E5 ב־0006:** בתוך baseline של Work,‏ `v2_reference_checkpoint=4` ו־`v2_reference_records=2000`, בעוד `similarity.indexed_records=2500`. שדה זה אינו מבהיר לבדו את הרכב האינדקס; לא ניתן לקבוע מהדוח שכל הייצור עד 0005 נכלל. נשמר הפער כגבול ראיה. דגל completed אינו סוגר את חסם הסריקה והכרעת הזוגות בעותק Work המעודכן.
3. **SHA ב־Windows:** ההשוואה הראשונית לבתי הקבצים המקומיים נכשלה בשני קובצי 0006. `core.autocrlf=true` ו־`git ls-files --eol` הראו Git עם LF ו־checkout עם CRLF. SHA-256 של בתי Git ושל עותק מקומי לאחר המרת CRLF ל־LF תואם בדיוק לדוחות: Chat `708f957d66d826a3ba535b1b4adcc48ad2b1c5d9aeb651f3184f6af350ca48e6`; Work `aa54df5dcbd2da9857c13dae5f571ba2cabf428573712076fb63b6c3d3493df7`. אין ראיה לשינוי תוכן; אין לטעון שה־hash הגולמי של checkout תואם. לא שונו קבצים או הגדרות Git כדי ליישר hashes.
4. **עקיבות דוחות:** חישוב hashes נוכחיים מקבע את הקבצים שנקראו; אין ב־0007–0009 hash מועמדים מוצהר בדוחות שנבדקו. עקביות ההפניות והספירות אינה הוכחה קריפטוגרפית שהביקורת ההיסטורית התבצעה על אותם בתים.
5. **תוכן וקליטה:** נותרו ביקורת עצמאית של תוויות ותחומים, השלמת ביקורת 0006 ותיקוניה, טיפול עריכתי ב־0007–0009, בדיקות סמנטיות והכרעות זוגות, ואימות מול מצב הייצור הרלוונטי. אלה חסמי המנות; טיפול תוכן ופרסום אינם חלק מהמשימה הנוכחית. אין לפתוח מחדש את מעמד 0001–0005 כדי לתעד אותם.

הסתירות במסמכי הניהול הוסרו: ההוראות הישנות להסדרת מנוע כתנאי פתיחה הוחלפו בהפניה להיקף שכבר אומת; הופרדו בדיקות תוכנה, שלמות מבנית ואיכות תוכן. פערי דוחות המקור לעיל נשמרו במפורש, ולא שונו בדיעבד.

## פקודות, תיעוד והמשך

- לפני העבודה: `git status --short --branch`,‏ `git worktree list`,‏ `git log -1 --oneline` ו־`git rev-parse HEAD` בשני עצי העבודה; קריאת ארבעת מסמכי הניהול ו־AGENTS בשניהם.
- בדיקה מקומית: `.venv-dev/Scripts/python.exe -B .poc-local/batch-status-2026-11-19/inspect_structure.py` — סיום 0,‏ 22 קבצים, 2,500 מועמדים ו־25 שורות ביקורת; אפס כשלים לאחר בירור הבדלי סיומות השורה.
- בירור hashes: `git show HEAD:<path>`,‏ `git hash-object`,‏ `git ls-files --eol` ו־`git config --get core.autocrlf`; הושוו בתים גולמיים, בתי Git והמרת LF ללא כתיבה לקובצי המקור.
- בדיקות התיעוד: `.venv-dev/Scripts/python.exe -B scripts/check_infrastructure.py` ו־`git diff --check`; התוצאות מרוכזות ב־[TECHNICAL_STATUS.md](../../TECHNICAL_STATUS.md).
- לא הורצו מחדש סוויטות יחידה, E5, בדיקות מטמון, בדיקות איכות, prepare/verify/checkpoint או פרסום רשומות; אין טענה ל־CI חדש שעבר. פעולת Git push נועדה למסמכי הסקירה בלבד.
- קבצים לשינוי: דוח זה וארבעת מסמכי הניהול. SHA סיום ותוצאת push יימסרו בהודעת הסיום. ענף הטיוטות נקרא בלבד.

## מצאי בתי Git — SHA-256

הערכים להלן מזהים את בתי Git עם LF שנקראו בשני בסיסי ה־SHA לעיל; ערכי checkout עשויים להיות שונים בגלל CRLF. הסימון `DB` מציין SentinelAI-DB, והסימון `Producer` מציין SentinelAI-Producer.

| Tree | File | SHA-256 of Git bytes |
|---|---|---|
| DB | `drafts/work/batch-0006/blind-review.jsonl` | `4345616b784900712769cd2e78edf5c9372bda7d132b5b85cb69f8ea341329c2` |
| DB | `drafts/work/batch-0006/candidates.jsonl` | `aa54df5dcbd2da9857c13dae5f571ba2cabf428573712076fb63b6c3d3493df7` |
| DB | `drafts/work/batch-0006/qa-report.json` | `d672bb90876a49afcbd16df0a74c8566a2c66e8c8c46b930abeeaf4d64fbd246` |
| DB | `drafts/work/batch-0006/status.json` | `40c1fd94ddb30200280cbc7a36cf32caf4fbf9dedb76d091c0bc4e1037472b11` |
| Producer | `drafts/chat/batch-0006/candidates.jsonl` | `708f957d66d826a3ba535b1b4adcc48ad2b1c5d9aeb651f3184f6af350ca48e6` |
| Producer | `drafts/chat/batch-0006/qa-report.json` | `3fe8c96a15f200ec0450c2c861d789e10a980669a5093f1f19669ef966e14c26` |
| Producer | `drafts/chat/batch-0006/status.json` | `92406a45d4db1f9fdef18ab8821256a2414507b91fcd7e1295f0a40d5ff2383c` |
| Producer | `drafts/chat/batch-0007/candidates.jsonl` | `358087acaaf86964ad9cd00c36195dd8d8b90fef0bdb86e91743de058bdf745b` |
| Producer | `drafts/chat/batch-0007/diversity-audit.json` | `76bce31b26a5af4d976e327d0dcee4c82599367ca6d4708d1e80de0afc03f84a` |
| Producer | `drafts/chat/batch-0007/qa-report.json` | `a37196199f00e89bead46d20631465e0381f26c5f28c2fdd30c6fc47b0e4f794` |
| Producer | `drafts/chat/batch-0007/remediation-queue.json` | `7a8eddfd3640fe2ab58dfc2b131dad7b4e243dbd19b60307918c78b8732c1628` |
| Producer | `drafts/chat/batch-0007/status.json` | `b81aa2961a5e43679ea61ecc93fb39d20b1979ca45d035aa538f676b8248d52e` |
| Producer | `drafts/chat/batch-0008/candidates.jsonl` | `89fa5499779151536d61943d6eee984d234ee8c30560afc4029254eb1a815636` |
| Producer | `drafts/chat/batch-0008/diversity-audit.json` | `3804bb15d9854cb43d8f7ef753217160c7012048e024e8a0cc13b46ddf4b4e65` |
| Producer | `drafts/chat/batch-0008/qa-report.json` | `6681a5724608f766766d50a2f771046b93df6fd9506eddcba5b85db2620f8126` |
| Producer | `drafts/chat/batch-0008/remediation-queue.json` | `f532f7b8221276d8bb3cd612fd826dc10576b6d9a2e3d6b1c6b9c353fd4a0841` |
| Producer | `drafts/chat/batch-0008/status.json` | `cacffc9f338969101813c3543324f06f6de76324a68aff89df58f0aa95893b62` |
| Producer | `drafts/chat/batch-0009/candidates.jsonl` | `d803abcbf56433461035239c7fffeaf66fe7a44592057edde0008208ea8fb6b2` |
| Producer | `drafts/chat/batch-0009/diversity-audit.json` | `0bc7a6a4db26ed04c41f0c095cb69edfd243edb46a6a78bbaae65b32e4c56691` |
| Producer | `drafts/chat/batch-0009/qa-report.json` | `a6c734f8108c00b0bf3c055795d1a578ce375ff52c66887cfe2d2af9c9d1b859` |
| Producer | `drafts/chat/batch-0009/remediation-queue.json` | `5e1936dc8ce266da264623b485876fbd80d1d2d8a023ddfaa98b04578d99b51f` |
| Producer | `drafts/chat/batch-0009/status.json` | `90078543d1a2ac13f2e30cae0034162904f5a68e9e7f9b0147bc8c3eff9e1c50` |
