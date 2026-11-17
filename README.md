# SentinelAI-DB

תהליך ייצור ושחזור של מאגר POC לסיווג רגישות טקסט בעברית. ארבע הרמות הן נמוך, בינוני, גבוה וחמור. הטקסטים הפנימיים בדיוניים. היעד הוא 100,000 רשומות מאוזנות.

| מסמך | תוכן |
|---|---|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | מצב ניהולי ומקורות אמת |
| [TECHNICAL_STATUS.md](TECHNICAL_STATUS.md) | בדיקות תשתית וחסמים |
| [WORK_COORDINATION.md](WORK_COORDINATION.md) | תיאום והעברת אחריות |
| [AGENTS.md](AGENTS.md) | כללי עבודה במאגר |
| [HANDOFF.md](HANDOFF.md) | מסמך ייצור היסטורי; יש להשוות ל־progress.json |
| [מדיניות התיוג](policy/v0.1.0.md) | הגדרות רגישות, הכרעות ומקרי קצה |
| [מכסות התחומים](config/defense-domain-targets.json) | 60% תוכן שעוסק מהותית במערכות טיליות |
| [הוראות הייצור](prompts/WORKER_START_DEFENSE_V2.md) | כתיבה, בידוד הארכיון ושיתוף עבודה |
| [מניפסט הארכיון](archive/general-v1/archive-manifest.json) | מאגר v1 שנשמר בצד |

## פתיחה ושחזור

הוראות ובדיקות התשתית להלן שייכות לענף הייצור `poc/defense-focused-v2`. לענף הטיוטות `producer/chat-defense-v2` יש README ו־AGENTS מקומיים עם הפניות למסמכי הניהול כאן; הוגדרו בו גם Python 3.13 והחרגות פיתוח, אך בודק התשתית וה־workflow לא הועברו אליו.

סדרת Python המוסכמת לפיתוח כללי היא **3.13**, עם עדכון patch בתוך הסדרה. המקור הוא [.python-version](.python-version); גם CI קורא אותו. ההרצות המקומיות האחרונות השתמשו ב־3.13.14. זו אינה נעילה של סביבת מנוע הדמיון או התחייבות לתאימות כל תלויותיו.

דרושים Git ו־Python 3.13 עם מודול `venv`. התחילו משורש checkout של ענף `poc/defense-focused-v2`. פקודת clone משותפת לשתי המערכות:

```bash
git clone --branch poc/defense-focused-v2 https://github.com/gal-dd/SentinelAI-DB.git
cd SentinelAI-DB
```

### Windows — PowerShell

```powershell
py -0p
py -3.13 -m venv .venv-dev
.\.venv-dev\Scripts\python.exe --version
.\.venv-dev\Scripts\python.exe -B scripts/check_infrastructure.py
.\.venv-dev\Scripts\python.exe -B -m unittest discover -s tests -p test_infrastructure.py -v
```

אפשר להפעיל `./.venv-dev/Scripts/Activate.ps1` ואז להשתמש ב־`python`; ההפעלה אינה חובה ואין צורך לשנות ExecutionPolicy. אם יצירת הסביבה או בדיקות זמניות נכשלות ב־`PermissionError`, בדקו הרשאות לתיקיית העבודה ול־Windows Temp; זו אינה בהכרח שגיאת קוד.

### Linux — Bash

התקינו Python 3.13 ו־venv באמצעות מנהל המערכת/החבילות המתאים להפצה. אם `python3.13 -m venv` מדווח ש־ensurepip/venv חסר, התקינו את חבילת venv התואמת. אין להחליף את Python של מערכת ההפעלה.

```bash
python3.13 -m venv .venv-dev
.venv-dev/bin/python --version
.venv-dev/bin/python -B scripts/check_infrastructure.py
.venv-dev/bin/python -B -m unittest discover -s tests -p test_infrastructure.py -v
```

אפשר להפעיל `source .venv-dev/bin/activate` ואז להשתמש ב־`python`. אין צורך ב־`pip install` לצורך פיתוח ובדיקות התשתית הכלליות. `.venv-dev/` מוחרגת מ־Git; אין להעתיק סביבה ממחשב או ממערכת הפעלה אחרת. אם קיימת `.venv` ממפרש אחר, השאירו אותה ובחרו במפורש את המפרש של `.venv-dev`.

### בדיקות תוכנה כלליות

הפקודה האחידה משורש המאגר, באמצעות המפרש הנבחר, היא:

```bash
python -B scripts/check_infrastructure.py
python -B -m unittest discover -s tests -p test_infrastructure.py -v
```

הבודק משתמש בספרייה התקנית בלבד ומחזיר קוד יציאה שונה מאפס בכשל. הוא קורא קבצים מנוהלים ב־Git וגם קבצים חדשים שאינם מוחרגים, ללא הרצת קוד הפרויקט:

- תחביר כל קובצי Python, באמצעות compilation בזיכרון וללא bytecode.
- UTF-8 ו־JSON תחת `config/`, כולל דחיית מפתחות כפולים ו־NaN/Infinity. נתונים, מטא־דאטה, דוחות וטיוטות אינם מפוענחים.
- קיום יעדים מקומיים בקישורי Markdown inline ובתמונות, במסמכי השורש ותחת `docs/`. קישורים יחסיים נפתרים מתיקיית המסמך; קישורים חיצוניים וקוד אינם נבדקים. נבדק קיום הנתיב בלבד, ללא anchors, קישורי reference, HTML או יעדים עם סוגריים מקוננים. מסמכי ארכיון, פרומפטים ומדיניות אינם נסרקים.

ב־[workflow התשתית](.github/workflows/infrastructure.yml) אותן שתי פקודות רצות על Windows ו־Ubuntu ב־Python 3.13, ב־push וב־pull request לענף הייצור. ההרשאות הן `contents: read`; אין התקנת מנוע, הורדת מודל או הרצת תהליך ייצור. אין זו בדיקת תוכן או כשירות לפרסום.

להרצת כל בדיקות היחידה הקיימות בענף הנוכחי:

```bash
python -B -m unittest discover -s tests -v
```

סוויטת ענף הטיוטות עשויה להזדקק לתלויות המנוע ול־`SENTINEL_E5_MODEL_DIR`; אינה חלק מ־CI התשתית הזה. הוראות המנוע בהמשך נפרדות מהקמת סביבת הפיתוח הכללית.

### מבנה המאגר ושחזור נתונים

| נתיב | תפקיד |
|---|---|
| `sentinel_dataset/` | קוד תהליך הנתונים וה־CLI |
| `scripts/`, `tests/` | כלי עזר ובדיקות תוכנה |
| `config/`, `policy/`, `prompts/` | הגדרות ותוכן מנוהלים; שינוי רק בהיקף שאושר |
| `data/`, `metadata/`, `reports/`, `drafts/` | נתונים, דוחות וטיוטות; אינם קבצים זמניים למחיקה |
| `archive/` | היסטוריית v1 השמורה ללא שינוי |
| `.poc-local/`, `.venv-dev/` | משאבים מקומיים המוחרגים מ־Git |

אימות הנתונים הוא פעולה נפרדת: `python -m sentinel_dataset verify` קוראת את `progress.json`, מאמתת SHA-256, התאמה בין הנתונים למטא־דאטה, מזהים רציפים ומכסות, ומחפשת כפילויות מנורמלות. נקודת ההמשך היא `next_id`. מצב הניהול נמצא ב־[PROJECT_STATUS.md](PROJECT_STATUS.md); יש להשוות את HANDOFF ההיסטורי למצב ההתקדמות הנוכחי.

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
{"scenario_id":"YOUR_REGISTERED_SCENARIO","primary_domain":"missile_systems","label":"בינוני","length":"sentence","origin":"synthetic","count":8}
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
