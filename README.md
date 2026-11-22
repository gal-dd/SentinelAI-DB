# SentinelAI-DB

תהליך ייצור ושחזור של מאגר POC לסיווג רגישות טקסט בעברית. ארבע הרמות הן בלמס, שמור, סודי וסודי ביותר. הטקסטים הפנימיים בדיוניים. היעד הוא 100,000 רשומות מאוזנות.

| מסמך | תוכן |
|---|---|
| [HANDOFF.md](HANDOFF.md) | מצב ההתקדמות ופקודות המשך |
| [מדיניות התיוג](policy/v0.1.0.md) | הגדרות רגישות, הכרעות ומקרי קצה |
| [מכסות התחומים](config/defense-domain-targets.json) | 60% תוכן שעוסק מהותית במערכות טיליות |
| [הוראות הייצור](prompts/WORKER_START_DEFENSE_V2.md) | כתיבה, בידוד הארכיון ושיתוף עבודה |
| [מניפסט הארכיון](archive/general-v1/archive-manifest.json) | מאגר v1 שנשמר בצד |

## פיתוח בענף הטיוטות

מסמך זה נמצא בענף `producer/chat-defense-v2`. קראו תחילה [AGENTS.md](AGENTS.md) ואת [מסמכי הניהול בענף הייצור](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/PROJECT_STATUS.md). Python המוסכם לפיתוח כללי הוא **3.13**; המקור הוא [.python-version](.python-version).

Windows/PowerShell, משורש checkout זה:

```powershell
py -3.13 -m venv .venv-dev
.\.venv-dev\Scripts\python.exe --version
```

Linux/Bash, לאחר התקנת Python 3.13 ו־venv המתאים להפצה:

```bash
python3.13 -m venv .venv-dev
.venv-dev/bin/python --version
```

אין צורך להפעיל venv אם משתמשים במפרש במפורש, ואין להעתיק סביבה בין מחשבים. `.venv-dev`, מפתחות ותוצרים מקומיים מוחרגים מ־Git. סוויטת ענף זה דורשת גם תלויות מנוע: בסקירה הקודמת 20 בדיקות עברו וטעינת מודול המטמון נכשלה בגלל numpy חסר; אין להציג את כל הסוויטה כעוברת. בדיקת E5 דורשת גם נכסי מודל ו־`SENTINEL_E5_MODEL_DIR`. לא בוצעה כאן התקנה או הרצה חוזרת.

בודק התשתית ו־GitHub Actions קיימים בענף הייצור בלבד; פקודותיו אינן זמינות ב־checkout זה. תוצאות, בדיקות שלא בוצעו וחסמים מרוכזים ב־[TECHNICAL_STATUS.md המרכזי](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/TECHNICAL_STATUS.md).

ההוראות הבאות מתארות את תהליך הנתונים וכוללות פקודות לענף הייצור. הן אינן הרשאה לייצר או לפרסם נתונים מתוך ענף הטיוטות.
## שחזור ייצור — בענף הייצור בלבד

לפיתוח כללי השתמשו ב־Python 3.13 וב־Git. יש לבצע את פקודות שחזור הייצור הבאות ב־checkout נפרד של ענף הייצור. הפקודות הבאות מתאימות ל־Bash. ב־PowerShell אפשר להשתמש בנתיבים רגילים ולהגדיר משתני סביבה באמצעות `$env:VARIABLE`.

```bash
git clone --branch poc/defense-focused-v2 https://github.com/gal-dd/SentinelAI-DB.git
cd SentinelAI-DB
python -m sentinel_dataset verify
```

הבדיקה קוראת את `progress.json`, מאמתת SHA-256, התאמה בין הנתונים למטא־דאטה, מזהים רציפים ומכסות, ומחפשת כפילויות מנורמלות. נקודת ההמשך היא `next_id`. השתמשו ב־`git log -1 -- HANDOFF.md` כדי לאתר את commit ההתקדמות האחרון. אם עובדים באמצעות GitHub API, צרו עץ מלא מול ה־HEAD הקיים, commit בן יחיד, ועדכנו את הענף ב־fast-forward. קראו שוב את ראש הענף ואמתו את ה־SHA.

## התקנת מנוע הדמיון המקומי

```bash
python -m pip install -r requirements-semantic.txt
mkdir -p .poc-local/e5
revision=761b726dd34fb83930e26aab4e9ac3899aa1fa78
base="https://huggingface.co/Xenova/multilingual-e5-small/resolve/$revision"
curl -fL "$base/tokenizer.json" -o .poc-local/e5/tokenizer.json
curl -fL "$base/onnx/model_int8.onnx" -o .poc-local/e5/model_int8.onnx
```

המודל רץ מקומית ב־CPU. השתמשו בקבצים של הגרסה המצוטטת. דוחות איכות כוללים SHA-256 של קובצי המודל. מנוע ה־E5 מחשב embedding של הטקסט, ומחפש שכנים בקוסינוס. עד 3,000 פריטים החיפוש מדויק, ובמאגר גדול יותר הוא משתמש ב־HNSW. החיפוש בודק עד 12 שכנים לרשומה. במקביל המערכת בודקת טקסט מנורמל, דמיון תווי ותבניות אחרי הפשטת מספרים ומונחים מסומנים במרכאות. סף דמיון מסמן מועמדים לקריאה חוזרת. החלטה על כפילות תלויה בתוכן.

## יצירת מנת ייצור

אפשר להתחיל ייצור כשהמאגר ריק. הפיילוט של v1 נשמר בארכיון ומחוץ לכל בדיקות v2. קובץ האימון הסופי נבנה מ־100,000 רשומות הייצור.

הריצו `python -m sentinel_dataset plan` לקבלת מכסות המנה לפי הספירה המצטברת. עם קובצי מועמדים קיימים, הפקודה מציגה גם יתרה לכל תא. `prepare` ו־`checkpoint` בודקים התאמה להקצאה. קראו את [הנחיות הכתיבה](prompts/defense-domain-production.md) לפני הפקת פסקאות ומסמכים.

לפני יצירת כל קבוצת מועמדים, תכננו עובדות, דרגות אפשריות וסגנון. רשמו תרחיש ב־`config/scenarios.json`. אם עובדה או חומר מקור משותפים לכמה תרחישים, הגדירו להם אותו `source_group_id`. שמרו ב־Git את קטלוג התרחישים והמקורות ששימשו במנה. קובצי הביניים המקומיים יכולים להישמר תחת `.poc-local/`.

בסביבת Work, GPT מחבר את הדוגמאות סמנטית לפי [חוזה הפרומפט](prompts/v0.1.0.md), ומזין אותן לבדיקות מקובצי JSONL. Python מטפל בבדיקות, מטא־דאטה, ביקורת, שחזור ו־Git. אפשר גם להריץ את המתאם האופציונלי מול API תואם OpenAI. משתנה `DATASET_MODEL_BASE_URL` מקבל את כתובת הבסיס, לדוגמה `http://127.0.0.1:11434/v1` עבור שרת מקומי תואם. אם השרת דורש אימות, ספקו `DATASET_MODEL_API_KEY` מחוץ לריפו. המסלול של Work זמין ללא התקנה או מפתח מצד המשתמש.

דוגמת `.poc-local/job.json`:

```json
{"scenario_id":"YOUR_REGISTERED_SCENARIO","primary_domain":"missile_systems","label":"שמור","length":"sentence","origin":"synthetic","count":8}
```

אפשר להגדיר `labels` במקום `label` עבור קבוצה שמכילה יותר מרמה אחת. זוג נגדי חייב להופיע בשלמותו באותה קריאה ובאותה מנת checkpoint. שמרו כל קריאה בקובץ נפרד. הכניסו למנה 500 מועמדים בדיוק אחרי סינון מקדים, בהתאם למכסות שנותרו ב־`config/plan.json` ובפלט `verify`.

```bash
python -m sentinel_dataset generate .poc-local/job.json .poc-local/part-01.jsonl --model GENERATOR
python -m sentinel_dataset prepare .poc-local/batch-0001.jsonl --model-dir .poc-local/e5 --packet .poc-local/packet.json
python -m sentinel_dataset review .poc-local/packet.json .poc-local/review.json --model REVIEWER
python -m sentinel_dataset checkpoint .poc-local/batch-0001.jsonl --decisions .poc-local/review.json --model-dir .poc-local/e5
```

הביקורת מקבלת טקסט בלי התווית המוצעת. היא מכסה מדגם של 10% ובו דוגמה אחת לפחות מכל תא פעיל של סיווג ופסקה או טקסט ארוך. ביקורת תחום נפרדת בוחנת את הנושא המרכזי בטקסט אחד לפחות מכל צירוף תחום וסיווג, בלי לראות את התחום המוצהר. בנוסף נסקרים מקרי קצה, זוגות נגדיים והתראות דמיון. כאשר שיעור אי־ההסכמה המתועד במנה הקודמת עולה על 5%, המדגם עולה ל־20%. אפשר לספק החלטות ממקור אחר באותו מבנה. אם נמצאה אי־הסכמה, פסילה או כפילות, תקנו את המועמדים והפיקו שוב את חבילת הביקורת. העבירו ל־`previous_attempts` את `reviewed`, `disagreements`, `rejected` ו־`corrected` של כל סבב קודם. ה־checkpoint שומר מדדים ונימוקים ומעדכן את ההתקדמות באותו commit.

אם התהליך נעצר אחרי commit ולפני אימות מרחוק, הריצו `python -m sentinel_dataset publish`. אם נותרו קבצים לא משויכים אחרי עצירה לפני commit, השוו אותם ל־`HEAD` ושמרו אותם זמנית אם דרושים לבדיקה. פתחו checkout נקי והשתמשו במועמדים ובהחלטות המקוריים כדי להריץ שוב. בעת דחיית push בשל שינוי בענף, בדקו את המנה שפורסמה והכינו מחדש רק מועמדים שאינם שמורים. הפקודה משתמשת ב־fast-forward ומאמתת את SHA ראש הענף מרחוק.

בסביבה שבה GitHub זמין דרך מחבר, הריצו `stage-checkpoint` עם הארגומנטים של `checkpoint` ועם `--output-dir .poc-local/staged`. הפקודה כותבת את הנתונים, המטא־דאטה, הדוח, `progress.json` ו־`HANDOFF.md` לתיקייה זמנית. פרסמו אותם יחד בקומיט אחד המבוסס על ראש הענף שנקרא, אמתו את ה־SHA וקראו מחדש את מצב ההתקדמות. אם ראש הענף התקדם בינתיים, הכינו מחדש את המנה מול המצב המרוחק.

## איחוד

```bash
python -m sentinel_dataset finalize --model-dir .poc-local/e5
```

הפקודה בודקת את כל המנות, מחשבת מחדש את ההתפלגות ואת הדמיון, ומייצרת מערך JSON ב־UTF-8 עם `ID`, `אובייקט` ו־`סיווג` בלבד. אם נמצאו התראות חדשות בסריקה הסופית, הפקודה כותבת קובץ לסקירה תחת `.poc-local/`. לאחר סקירה מעבירים מיפוי ממזהה התראה ל־`{"status":"keep","reason":"…"}` דרך `--dispositions`. את החלוקה העתידית מבצעים לפי `source_group_id` מהמטא־דאטה, לפני הסרת המטא־דאטה מקלט האימון.
