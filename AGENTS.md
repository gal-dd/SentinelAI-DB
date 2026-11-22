# כללי עבודה — ענף הטיוטות

ענף העבודה כאן הוא `producer/chat-defense-v2`; ענף הייצור הוא `poc/defense-focused-v2`. אמתו תחילה `git status --short --branch`,‏ `git worktree list` ו־`git log -1 --oneline`. אין למזג ענפים כחלק מתחזוקה.

## מקורות אמת

מסמכי הניהול המרכזיים נשמרים בענף הייצור, ללא העתקים מקומיים שעלולים להתיישן. קראו אותם בתחילת שיחה:

- [AGENTS.md — הכללים המרכזיים](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/AGENTS.md)
- [PROJECT_STATUS.md](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/PROJECT_STATUS.md)
- [TECHNICAL_STATUS.md](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/TECHNICAL_STATUS.md)
- [QUALITY_STATUS.md](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/QUALITY_STATUS.md)
- [WORK_COORDINATION.md](https://github.com/gal-dd/SentinelAI-DB/blob/poc/defense-focused-v2/WORK_COORDINATION.md)

אם תיקיית SentinelAI-DB זמינה ליד תיקייה זו, אפשר לקרוא משם לאחר אימות הענף. אחרת אפשר לקרוא מ־GitHub או מ־`git show poc/defense-focused-v2:PROJECT_STATUS.md` כאשר הענף זמין מקומית. אין להסתמך על היסטוריית שיחה. HANDOFF כולל הפניה למקור האמת; יתר תוכנו היסטורי.

## היקף ופיתוח

- Python לפיתוח כללי: סדרת 3.13, לפי `.python-version`. הוראות הקמה ב־[README.md](README.md). סביבת פיתוח ללא חבילות מנוע אינה מספיקה לכל בדיקות ענף זה.
- בודק התשתית וה־CI מוגדרים בענף הייצור; אין להפעיל כאן פקודה המפנה לקובץ שאינו קיים או לטעון שבדיקות הייצור מאמתות את ענף הטיוטות.
- במסגרת תחזוקה כללית אין לשנות נתונים, טיוטות, פרומפטים, מנגנוני ייצור, איכות תוכן או מדיניות סיווג. אין לפרסם טיוטות ללא משימה ואישור מתאימים.
- אל תדרסו שינויים קיימים. שמרו סביבות, מפתחות, מודלים ותוצרים זמניים מחוץ ל־Git. אין למחוק תוצרים או ארכיון לצורך ניקוי שגרתי.
- פעלו בגישת KISS, עם כלים מקומיים וקריאה ממוקדת. אל תחזרו על בדיקות שהושלמו ללא שינוי רלוונטי. בדקו diff ו־`git diff --check` לפני commit; בצעו commit/push כשאושרו, ללא force push.

## העברת אחריות

תעדו במסמכי הניהול המרכזיים ענף, SHA בסיס, קבצים ששונו, פקודות ותוצאות בפועל, בדיקות שלא הורצו וחסמים. ציינו SHA סיום ותוצאת push בהודעת הסיום. הצלחת תשתית אינה אישור לאיכות תוכן או לפרסום.

## שמות סיווג החל מ־2026-11-22
הסיווגים התקניים לייצור חדש: בלמס, שמור, סודי, סודי ביותר. החלפת שמות אינה שינוי רגישות. מיגרציית הנתונים והבדיקות הישנות טרם הושלמה; אין לפרסם טיוטות דרך מנוע לא מעודכן או לטעון שנעשתה מיגרציה מלאה.
