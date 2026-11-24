# חוזה משימה אחיד לעובד חדש

מנהל אחד מתאם את העבודה. מזהי משימה אינם מספרי checkpoint; הם מזהי עבודה זמניים, ייחודיים לכל עובד. המנהל מקצה אותם לפני תחילת עבודה ומחזיק רשימת הקצאות אחת. ניתן להכין כמה תוצרים במקביל, אך אין לפרסם נתונים באופן מקביל.

```json
{
  "task_id": "20261125-01",
  "owner": "worker-alias",
  "role": "documentation",
  "base_branch": "poc/defense-focused-v2",
  "base_commit": "actual SHA from the coordinator",
  "scope": "one explicitly authorized safe task",
  "output_path": "collaboration/submissions/20261125-01/",
  "status": "assigned"
}
```

תפקידים אפשריים: `documentation` (מסמכים), `infrastructure` (תוכנה כללית ובדיקות מבודדות), `public_content` (תוכן ציבורי/בדיוני בטוח שאושר להיקף המשימה), `review` (ביקורת תוצר בטוח ומצומצם שסופק במפורש). מנהל הפרויקט בלבד אחראי לקליטה ולפרסום.

אם אושרה גישת כתיבה מוגבלת, שם ענף העבודה הוא `collab/<task_id>`; התחילו מ־SHA שאושר, ואל תכתבו לענף בסיס. אם אין הרשאה מתאימה, החזירו את התוצר כקובץ. אין לקרוא או לשכתב תוצרים של עובדים אחרים ללא הקצאה. אין להתקין שירותי צד שלישי או לשנות workflows בעלי הרשאת כתיבה בלי אישור.

## חוזה מסירה
```json
{
  "task_id": "20261125-01",
  "status": "ready_for_review",
  "base_commit": "actual SHA",
  "output_paths": [],
  "commit_sha": null,
  "checks_run": [],
  "checks_not_run": [],
  "limitations": [],
  "blockers": []
}
```

סטטוסים: assigned, in_progress, ready_for_review, blocked, accepted. אין לסמן accepted בלי החלטת המנהל. בביקורת ציינו מודל וספק, האם ראה תוויות קודמות, וגבולות האימות; בדיקת תוכנה אינה ביקורת תוכן. אין לסמן בדיקה כעברה אם לא הורצה. אם בסיס העבודה השתנה, אין לדרוס או למזג אוטומטית: יש למסור תוצר ולתעד את בסיסו.
