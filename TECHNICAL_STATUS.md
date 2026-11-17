# TECHNICAL_STATUS — תשתית תוכנה כללית

תאריך: 2026-11-17. הסבב הנוכחי מגדיר סביבת פיתוח ובדיקות תחזוקה; אינו אישור לאיכות תוכן, כשירות מנוע הדמיון או פרסום נתונים.

## בסיס העבודה וענפים

נקראו מסמכי הניהול וסקירת התשתית הקודמת, שנדחפה ב־`d038ff819954defdc7514162b6ef7ed364b262c0`. זו נקודת הבסיס של השינויים הנוכחיים. הפירוט ההיסטורי של הסקירה הקודמת נשמר באותו commit.

| תיקייה | ענף | HEAD בתחילת הסבב | מצב התחלתי |
|---|---|---|---|
| SentinelAI-DB | `poc/defense-focused-v2` | `d038ff819954defdc7514162b6ef7ed364b262c0` | נקי |
| SentinelAI-Producer | `producer/chat-defense-v2` | `128fd6e25495afc095dfe6be757e46d0bf22a10b` | נקי |

אומתו `git status`,‏ `git worktree list` ו־`git log`. השינויים נעשו בענף הייצור בלבד, ללא מיזוג. ענף הטיוטות נשאר ללא שינוי.

## סביבת פיתוח מוסכמת

- `py -0p` ו־`py -3.13/3.14/3.15 --version` בוצעו בפועל: מותקנות ופועלות **3.13.14, 3.14.4, 3.15.1**. ברירת המחדל של `python` היא 3.15.1.
- נבחרה **סדרת Python 3.13** לפיתוח הכללי. `.python-version` מכיל `3.13`; עדכוני patch מותרים. הבחירה משתמשת במפרש שכבר מותקן ואומתה מקומית; אינה קביעה לגבי תאימות חבילות המנוע או נעילה מלאה של סביבתו.
- נוצרה `.venv-dev` באמצעות `py -3.13 -m venv .venv-dev`. אומתה גרסה 3.13.14; `pip list` מציג pip 26.1.2 בלבד. לא נדרשה התקנת חבילה חיצונית. `.venv` הישנה של 3.15.1 נשמרה.
- הקמת venv נכשלה תחילה בשלב ensurepip בסביבה המוגבלת; אותה פקודה הצליחה בהרשאה מורחבת. בדיקות המשתמשות ב־Temp הורצו בהרשאה מורחבת, לאור כשלי ההרשאות שתועדו בסקירה הקודמת.
- README כולל הוראות Windows/PowerShell ו־Linux/Bash, שימוש במפרש מפורש ללא חובה להפעיל venv, והפרדה בין פיתוח כללי למנוע הדמיון.

## בדיקות תשתית ו־CI

נוסף `scripts/check_infrastructure.py`, בודק קריאה בלבד המבוסס על הספרייה התקנית. הפקודה האחידה: `python -B scripts/check_infrastructure.py`, משורש checkout. נבדקים קבצי Git וקבצים חדשים שאינם מוחרגים:

1. תחביר כל קובצי Python ב־compile בזיכרון, ללא import או הרצת קוד הפרויקט.
2. UTF-8 ו־JSON רק תחת `config/`, עם דחיית מפתחות כפולים ו־NaN/Infinity. נתונים, דוחות, מטא־דאטה וטיוטות אינם מפוענחים.
3. קיום יעדים מקומיים בקישורי inline ובתמונות במסמכי Markdown בשורש וב־`docs/`. נתיבים יחסיים נפתרים מתיקיית המסמך; קישורים החורגים מה־checkout נכשלים. אין פנייה לרשת או בדיקת anchors, קישורי reference, HTML או סוגריים מקוננים ביעדים. קוד בתוך fences ו־inline code מוחרג. מסמכי תוכן וארכיון אינם נסרקים.

נוספו שש בדיקות רגרסיה ב־`tests/test_infrastructure.py`: תחביר בלי ביצוע קוד; JSON פגום/כפילויות/קבועים; קישורים יחסיים ומקודדים והחרגת דוגמאות קוד; קישורים חסרים ויציאה מה־checkout; הגבלת היקף; גילוי קבצים חדשים והחרגת venv.

נוסף `.github/workflows/infrastructure.yml`: ב־push וב־pull request לענף הייצור, וכן בהפעלה ידנית, בדיקות התשתית ושש בדיקות הבודק רצות ב־`ubuntu-latest` וב־`windows-latest`, בגרסה מתוך `.python-version`. הרשאת `contents: read` בלבד ו־timeout של 10 דקות; ללא תלויות מנוע, נתוני בדיקה מהפרויקט או פעולות ייצור. גרסאות actions נבחרו לפי [checkout](https://github.com/actions/checkout) ו־[setup-python](https://github.com/actions/setup-python), המשתמשים בתיעוד הנוכחי ב־v7.

## בדיקות שבוצעו בסבב הנוכחי

| פקודה / בדיקה | תוצאה מקומית ב־Windows, Python 3.13.14 |
|---|---|
| `.venv-dev/Scripts/python.exe -B scripts/check_infrastructure.py` | עבר: 14 קובצי Python, ארבעה קובצי JSON, שבעה מסמכי Markdown |
| `.venv-dev/Scripts/python.exe -B -m unittest discover -s tests -v` | 13/13 עברו: שבע בדיקות קיימות ושש בדיקות תשתית חדשות |
| `git check-ignore` עבור venv ישנה/חדשה, pyc, env, מודל מקומי וקובץ tmp | כולם הוחרגו; `.env.example` נשאר ניתן להוספה |
| `git ls-files` עבור pyc/pyo, קבצים זמניים, env, logs, ONNX ו־SQLite | לא נמצאו קבצים כאלה מנוהלים |
| `git status --short --ignored` | לפני השינוי נמצאו רק venv ו־__pycache__ כתוצרים מוחרגים; לא נמחקו |
| `git diff --check` | עבר; יבוצע גם לפני commit |
| `wsl --list --quiet` | אחרי חסימת הרשאות והרצה חוזרת נמצא רק docker-desktop; לא בוצעה הרצת Linux מקומית |
| GitHub Actions, commit `bac487b` | עבר ב־Windows וב־Ubuntu: בודק התשתית ושש בדיקות הרגרסיה בכל מערכת |

לאחר push של `bac487ba74d457acf9181eadec5ac3389dcaf992`, אומת ראש הענף באמצעות `git ls-remote`. [הרצת CI מספר 1](https://github.com/gal-dd/SentinelAI-DB/actions/runs/44155155183) הסתיימה ב־`success`, כולל שני ה־jobs והצעדים שלהם. עדכון תיעוד זה מתעד את התוצאה שהתקבלה לאחר הפרסום; SHA הסיום יימסר בהודעת הסיום.

## תחזוקת המאגר ותיעוד

`.gitignore` הורחב לסביבות `.venv*`/`venv`, קובצי env מקומיים (למעט `.env.example`), bytecode, מטמוני בדיקות/lint, כיסוי, גיבויים זמניים וקובצי מערכת הפעלה. לא הוחרגו תיקיות הנתונים/טיוטות/דוחות/ארכיון. לא בוצע ניקוי או מחיקת קבצים קיימים.

המבנה הקיים נשמר ותועד בטבלה ב־README. נוסף `AGENTS.md` עם מקורות אמת, הגבלת היקף, פקודות בדיקה וכללי commit/push והעברת אחריות. README מפנה כעת למסמכי הניהול ומבהיר ש־HANDOFF היסטורי. `PROJECT_STATUS.md`,‏ `WORK_COORDINATION.md` ו־`QUALITY_STATUS.md` עודכנו כדי להבחין בין בדיקות תוכנה חדשות לבין הסקירה המנהלית/איכות התוכן שלא שונתה.

## חסמים שנותרו ומגבלות

- ארבע תלויות מנוע הדמיון ונכסי E5 לא הותקנו בסבב זה; `requirements-semantic.txt` וטווחי הגרסאות שבו נשארו ללא שינוי. אין lock/hashes לתלויות המנוע; זמינות wheels/כלי בנייה ותאימות runtime שלו ל־3.13 טרם אומתו.
- בסקירה הקודמת בענף הטיוטות עברו 20 בדיקות, וטעינת `test_embedding_cache` נכשלה בגלל numpy חסר (ארבע בדיקות במודול לא הורצו). הסוויטה לא הורצה מחדש בסבב זה, ו־`SENTINEL_E5_MODEL_DIR` לא הוגדר.
- בדיקות התשתית ושש בדיקות הרגרסיה אומתו ב־Linux וב־Windows ב־CI. תצורת YAML התקבלה והורצה ב־GitHub; הבודק המקומי עצמו אינו מאמת YAML. לא נבדקו הוראות התקנת Python בחלוקת Linux מסוימת או פרסום מקצה לקצה.
- לא נבדקו API אמיתי, ONNX/HNSW, נעילות פרסום, שלמות קריפטוגרפית של נתונים או איכות תוכן. `verify`, תהליכי ייצור ופרסום נתונים לא הורצו.

## העברת אחריות

השינויים הנוכחיים: `.gitignore`,‏ `.python-version`,‏ `.github/workflows/infrastructure.yml`,‏ `scripts/check_infrastructure.py`,‏ `tests/test_infrastructure.py`,‏ `AGENTS.md`,‏ `README.md`,‏ `PROJECT_STATUS.md`,‏ `WORK_COORDINATION.md`,‏ `QUALITY_STATUS.md` ומסמך זה. Commit ו־push לענף הייצור נכללים באישור המשתמש; SHA הסיום יימסר לאחר הביצוע. לא שונו נתונים, מנגנוני ייצור או איכות, פרומפטים, מדיניות סיווג או ענף הטיוטות.
