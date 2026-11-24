# TECHNICAL_STATUS — מצב פעיל

הפקודות והסביבה ב־[README](README.md). מקור האמת לענף ולספירה: `progress.json` בענף `poc/defense-focused-v2`.

- תהליך `verify` מאמת את חתימות הייצור ומזהי הרשומות; אינו ביקורת תוכן.
- תשתית כללית: Python 3.13, בדיקות תחביר/JSON/קישורים ומבחני תוכנה מבודדים. מנוע דמיון הוא סביבת תלות נפרדת.
- מנה 0014 נקלטה באמצעות `stage-checkpoint`. שדה התחום ב־500 התרחישים החדשים הושלם מהשיוך של המועמדים, והרצת `verify` אימתה את מצב הייצור. [דוח המנה](reports/checkpoints/batch-0014.json).
- פרסום 0013 נעשה באמצעות `stage-checkpoint`. פקודת `verify` אימתה את הרשומות החתומות, ומניפסט הייצוא אומת מול מטא־דאטת הייצור. [קומיט המנה](https://github.com/gal-dd/SentinelAI-DB/commit/d7646c891cfc8af463ca3a1d715c8badc4767232).
- פרסום 0012: [קומיט](https://github.com/gal-dd/SentinelAI-DB/commit/8c204edca37a35fd7b622cc551987372eea4bd19) ו־[ייצוא](exports/manifest.json). בהרצות קודמות של 0012 השתנו זוגות הדמיון שנבחרו ב־prepare. הפתרון שנבדק היה הכרעות מפורשות לזוגות שנצפו בפועל, לא הנמכת ספים או ביטול בדיקות. אין להעביר החלטות לזוגים שלא נבדקו.
- מסלול השיתוף החדש מוסיף נקודת כניסה, חוזה מסירה, גבול שיתוף, אינדקס היסטוריה ופקודת סטטוס מטא־דאטה בלבד. לא שינה מנוע איכות, מדיניות, מכסות או נתוני ייצור.
- היסטוריית ראיות וחסמים: [מסמך קודם](https://github.com/gal-dd/SentinelAI-DB/blob/e35d8e8b536392025e8c2d31f9d038062ec60617/TECHNICAL_STATUS.md).

בדיקות לתוספת החדשה: `python -B -m unittest discover -s tests -p test_collaboration_status.py -v`; תוצאות בפועל נבדקות ב־CI.
