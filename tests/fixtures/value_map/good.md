# Value map: Acme Clinics booking assistant

## 1. Scenario and boundary

The assistant books, moves and cancels appointments for the three Acme Clinics sites through the website and the phone line, answers price questions from the price list and sends visit reminders. It does not give medical advice, does not take payments and does not change the price list; the front desk keeps every call the assistant hands over.

## 2. Pillars and SLAs

| ID | Pillar | Metric | Threshold | Segment | Method | Consequence | Source |
|---|---|---|---|---|---|---|---|
| SLA-01 | efficiency | share of bookings the front desk does not have to correct | at least 95% | per site | weekly sample of 100 bookings, checked by the front desk lead | bookings go back to the front desk until the share recovers | NFR-004 |
| SLA-02 | cost | share of reminders delivered a day before the visit | at least 98% | per channel | daily delivery log | the front desk calls the patients the log shows as missed | our proposal |

## 3. Baseline

| Measure | Unit the business counts | Value now | Source | How it was obtained | Confidence |
|---|---|---|---|---|---|
| Booking calls handled by the front desk | calls a month | 6,000 calls/month | front desk phone log, July to September | client figure | high |
| Front desk time per booking call | minutes per call | 6 min | phone log and staffing table | timestamps: 5.5 min; staff top-down: 6.5 min | medium |
| Loaded cost of a front desk hour | currency per hour | $28/h | finance figure in the scope document | client figure | high |
| Missed visits | no-shows a month | 900 no-shows/month | scheduling system report, July to September | client figure | high |
| Average visit price | currency per visit | $90/visit | price list | client figure | high |

## 4. Value lines

| ID | Pain | Pillar | Now (formula) | With the solution (formula) | Monthly gain (formula) | Hard or soft | Condition and write-off | SLA |
|---|---|---|---|---|---|---|---|---|
| V-01 | P-01 | efficiency | 6,000 calls/month × 6 min × $28/h = $16,800/month | (6,000 calls/month × 60%* × 1* min + 6,000 calls/month × (1 − 60%*) × 6 min) × $28/h = $8,400/month | $16,800/month − $8,400/month = $8,400/month | soft | becomes money when front desk overtime stops; $8,400/month × (1 − 60%) = $3,360/month | SLA-01 |
| V-02 | P-02 | cost | 900 no-shows/month × $90/visit = $81,000/month | 900 no-shows/month × (1 − 25%*) × $90/visit = $60,750/month | $81,000/month − $60,750/month = $20,250/month | hard | | SLA-02 |
| V-03 | P-03 | transformation | same-day price answers 40% | same-day price answers 100% | not valued: the material gives no figure for a patient lost to a late answer | soft | | SLA-01 |

## 5. Run cost per month

| Item | Driver (formula) | Monthly cost | Source |
|---|---|---|---|
| Model tokens | 6,000 conversations/month × 8k tokens × $3/1M tokens = $144/month | $144/month | price list of the model provider, 2026-10-01; tokens per conversation from design section 5 |
| Hosting | 1 environment × $400/month = $400/month | $400/month | design section 6, provider price list 2026-10-01 |
| Front desk review of handed-over bookings | 300 bookings/month × 2 min × $28/h = $280/month | $280/month | A-03 |
| Evaluation sampling and maintenance | 4 h/month × $60/h = $240/month | $240/month | A-04 |

## 6. Net value and the break-even build budget

| Key | Formula |
|---|---|
| hard | $20,250/month |
| soft | $3,360/month |
| run | $144/month + $400/month + $280/month + $240/month = $1,064/month |
| net | $20,250/month + $3,360/month − $1,064/month = $22,546/month |
| budget-12 | $22,546/month × 12 month = $270,552 |
| budget-24 | $22,546/month × 24 month = $541,104 |

## 7. Sensitivity and the miss case

| Case | What changes | Net (formula) | Budget 12 (formula) | Budget 24 (formula) |
|---|---|---|---|---|
| Volume halved | calls and no-shows halve; tokens halve | ($20,250/month + $3,360/month) × 50% − ($144/month × 50% + $400/month + $280/month + $240/month) = $10,813/month | $10,813/month × 12 month = $129,756 | $10,813/month × 24 month = $259,512 |
| Review share doubled | front desk review doubles | $20,250/month + $3,360/month − ($144/month + $400/month + $280/month × 2 + $240/month) = $22,266/month | $22,266/month × 12 month = $267,192 | $22,266/month × 24 month = $534,384 |
| Accuracy SLA missed | 5% of online bookings need 10 minutes of rework | $22,546/month − 6,000 calls/month × 60%* × 5%* × 10* min × $28/h = $21,706/month | $21,706/month × 12 month = $260,472 | $21,706/month × 24 month = $520,944 |

## 8. Verdict

Worth building. The missed visits carry the case: $20,250 a month of hard gain against $1,064 of run cost, so a build budget up to $270,552 pays back in 12 months even before the front desk time is counted.

## 9. Assumption map

| ID | Assumption | Value (range) | Source | Confidence | How confirmed | Owner at the client | Impact if wrong |
|---|---|---|---|---|---|---|---|
| A-01 | Share of bookings made without the front desk | 60% (40–75) | similar clinic booking projects | low | shadow month on one site | front desk lead | strong |
| A-02 | Fewer no-shows with reminders | 25% (15–35) | public study of reminder programmes, URL in the extract | medium | phase 0 on one site, two months | operations manager | critical |
| A-03 | Bookings handed to the front desk and their review time | 300 bookings, 2 min (1–3) | our estimate | low | shadow month | front desk lead | minor |
| A-04 | Evaluation and maintenance time | 4 h (2–6) | our estimate | medium | first three months of operation | IT lead | minor |
| A-05 | Front desk time for an online booking it checks | 1 min (0.5–1.5) | our estimate | low | shadow month | front desk lead | minor |
| A-06 | Online bookings that need rework when the SLA is missed, and the rework time | 5% (3–8), 10 min (5–15) | our estimate | low | shadow month | front desk lead | strong |

No economic effect is committed before these are confirmed.

## 10. What the pilot measures

| Measure | Value line | Before | After, by the same definition | Control | Who measures |
|---|---|---|---|---|---|
| Front desk minutes on bookings a month | V-01 | 36,000 min from the phone log | the same log, same months a year later | a site without the assistant | front desk lead |
| No-shows a month | V-02 | 900 from the scheduling report | the same report | the same months a year earlier | operations manager |
| Same-day price answers | V-03 | 40% from the inbox sample | the same sample | the same sample size | front desk lead |
