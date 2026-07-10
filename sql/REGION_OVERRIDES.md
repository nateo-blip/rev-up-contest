# Region Overrides

The following reps have incorrect REGION values in FACT_FIELD_SALES_EMPLOYMENT_CURRENT.
Apply these corrections in any view or report:

| Rep | Manager | Snowflake Region | Correct Region |
|-----|---------|-----------------|----------------|
| William McQuaig | Phillip Skillern | East | **Central** |
| Matt Milos | Steve McMahon | Central | **East** |
| Erick Clausen | Ramon Quevedo | East | **Central** |
| Brady Katz | Steve McMahon | Central | **East** |
| River Sava | Alessandra Verne | East | **Central** |

## SQL Fix (add to WHERE or CASE statements):

```sql
CASE 
    WHEN FULL_NAME = 'William McQuaig' THEN 'Central'
    WHEN FULL_NAME = 'Matt Milos' THEN 'East'
    WHEN FULL_NAME = 'Erick Clausen' THEN 'Central'
    WHEN FULL_NAME = 'Brady Katz' THEN 'East'
    WHEN FULL_NAME = 'River Sava' THEN 'Central'
    ELSE REGION
END AS REGION
```
