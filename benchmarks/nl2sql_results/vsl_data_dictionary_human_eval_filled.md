> **⚠️ HISTORICAL SHEET — superseded in part. Authoritative verdicts are in `vsl_final_labels.csv`.**
>
> This sheet records the *original* generated SQL, expected behaviors, and verdicts. A later
> ground-truth audit (AI-assisted; the authors re-judged the affected cases) found that some original
> expectations and verdicts here were not supportable by the data and were **superseded**. For example,
> a record-counting query was credited for a density intent although the schema provides no denominator
> or area field to normalize by. The audit corrected eight condition-labels across six cases.
>
> **Use the corrected, authoritative labels in `vsl_final_labels.csv`.** Every change from these sheets
> is listed with a reason in `vsl_corrections_log.csv`. The original text below is preserved unchanged
> for traceability.

---

# VSL Human Evaluation Sheet — Data-Dictionary Baseline (D1, description-only)
Generated: 2026-10-16 03:45 UTC
Total cases: 124

Condition: agent + schema + plain column DESCRIPTIONS (reviewer-requested baseline, R3-W4). No VSTs.

**Verdict options**: `correct` / `partial` / `incorrect`

---

## Domain: finance

### finance_001 — comparative_grounding (medium)

**Intent**: Loans with unusually high principal amount given their loan status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
status
FROM loan
    WHERE amount >(
    SELECT AVG(amount) + 2 * STDDEV(amount)
    FROM loan
WHERE status = loan.status)
ORDER BY amount DESC;
```

**D1 Verdict**: `partial`  **Notes**: Inner status = loan.status refers to the inner table on both sides; threshold is global, not status-conditioned.

---

### finance_002 — comparative_grounding (easy)

**Intent**: Find unusually large withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT trans_id,
account_id,
date,
amount,
balance
FROM trans
WHERE type = 'debit'
AND amount > 10000;
```

**D1 Verdict**: `partial`  **Notes**: Uses withdrawal direction, but 10000 is an unsupported fixed cutoff.

---

### finance_003 — process_misinterpretation (medium)

**Intent**: Accounts with sustained negative balance

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Data-dictionary SQL
```sql
SELECT DISTINCT t.account_id
FROM trans t
    JOIN (
    SELECT account_id
    FROM trans
    GROUP BY account_id
HAVING SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) = COUNT(*)) AS negative_accounts
ON t.account_id = negative_accounts.account_id;
```

**D1 Verdict**: `partial`  **Notes**: Requires every recorded balance to be negative; allows a single observation and misses sustained negative episodes within otherwise positive histories.

---

### finance_004 — comparative_grounding (easy)

**Intent**: Find large loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
status
FROM loan
WHERE amount > 100000; -- Assuming "large loans" are those with an amount greater than 100,000
```

**D1 Verdict**: `partial`  **Notes**: Relevant amount filter, but assumes a fixed definition of large.

---

### finance_005 — comparative_grounding (medium)

**Intent**: Accounts with unusually frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
COUNT(t.trans_id) AS withdrawal_count
FROM account a
JOIN trans t
ON a.account_id = t.account_id
WHERE t.type = 'debit'
AND t.operation = 'withdrawal'
GROUP BY a.account_id
    HAVING COUNT(t.trans_id) >(
    SELECT AVG(withdrawal_count)
        FROM (
        SELECT COUNT(t2.trans_id) AS withdrawal_count
        FROM trans t2
        WHERE t2.type = 'debit'
        AND t2.operation = 'withdrawal'
GROUP BY t2.account_id) AS subquery)
ORDER BY withdrawal_count DESC;
```

**D1 Verdict**: `partial`  **Notes**: Counts withdrawals and compares accounts, but above-average frequency does not establish unusually frequent activity; withdrawal operation value also needs verification.

---

### finance_006 — role_confusion (hard)

**Intent**: Clients with highest account

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
COUNT(d.account_id) AS account_count
FROM client c
JOIN disp d
ON c.client_id = d.client_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 1;
```

**D1 Verdict**: `correct`  **Notes**: Counts associated accounts instead of ranking identifiers, as explicitly permitted.

---

### finance_008 — process_misinterpretation (hard)

**Intent**: Loans with payment irregularity

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Data-dictionary SQL
```sql
SELECT loan.loan_id,
loan.account_id,
loan.amount,
loan.duration,
loan.payments,
loan.status
FROM loan
WHERE loan.status <> 'A'
```

**D1 Verdict**: `incorrect`  **Notes**: A static status exclusion does not identify payment irregularity from event history.

---

### finance_009 — comparative_grounding (medium)

**Intent**: Loans with high amount but low repayment

**Expected behavior**: Use relative high/low cutoffs for both amount and repayment.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
status
FROM loan
WHERE amount > 100000
AND payments < 1000;
```

**D1 Verdict**: `partial`  **Notes**: Captures both comparative directions but uses arbitrary fixed thresholds.

---

### finance_010 — quantitative_misinterpretation (medium)

**Intent**: Loans with largest remaining balance

**Expected behavior**: Rank by estimated unpaid balance, not by original loan amount.

#### Data-dictionary SQL
```sql
SELECT l.loan_id,
l.account_id,
            l.amount -(l.payments *(EXTRACT(YEAR
            FROM CURRENT_DATE) - EXTRACT(YEAR
FROM l.date)) * 12) AS remaining_balance
FROM loan l
ORDER BY remaining_balance DESC
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Estimates unpaid balance, but year-only elapsed time ignores months, loan maturity, and actual repayments.

---

### finance_011 — role_confusion (medium)

**Intent**: Most important accounts

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
SUM(t.amount) AS total_transactions,
COUNT(DISTINCT l.loan_id) AS number_of_loans,
COUNT(DISTINCT o.order_id) AS number_of_orders
FROM account a
LEFT JOIN trans t
ON a.account_id = t.account_id
LEFT JOIN loan l
ON a.account_id = l.account_id
LEFT JOIN "order" o
ON a.account_id = o.account_id
GROUP BY a.account_id
ORDER BY total_transactions DESC,
number_of_loans DESC,
number_of_orders DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Uses plausible importance signals, but meaning remains unspecified; joining multiple one-to-many tables inflates transaction sums.

---

### finance_012 — process_misinterpretation (hard)

**Intent**: Accounts with increasing withdrawal frequency over time

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
    WITH withdrawal_counts AS(
    SELECT a.account_id,
    t.date,
        COUNT(*) FILTER(
    WHERE t.type = 'withdrawal') AS withdrawal_count
    FROM account a
    JOIN trans t
    ON a.account_id = t.account_id
    GROUP BY a.account_id,
t.date),
    withdrawal_trend AS(
    SELECT account_id,
    withdrawal_count,
        LAG(withdrawal_count) OVER(PARTITION BY account_id
    ORDER BY date) AS previous_withdrawal_count
FROM withdrawal_counts)
SELECT DISTINCT account_id
FROM withdrawal_trend
WHERE withdrawal_count > previous_withdrawal_count
ORDER BY account_id;
```

**D1 Verdict**: `partial`  **Notes**: Detects an increase between observed dates, but does not establish a sustained frequency trend or include missing dates.

---

### finance_014 — comparative_grounding (hard)

**Intent**: Loans with extreme duration compared to principal

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
status
FROM loan
WHERE duration > 60
AND amount < 10000
OR duration < 12
AND amount > 50000;
```

**D1 Verdict**: `partial`  **Notes**: Relates duration to principal, but uses fixed cutoffs and includes the opposite duration/principal pattern.

---

### finance_015 — quantitative_misinterpretation (medium)

**Intent**: Loans with high repayment ratio

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
(amount /(duration * payments)) AS repayment_ratio
FROM loan
WHERE (amount /(duration * payments)) > 1
ORDER BY repayment_ratio DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Inverts the intended repayment-to-principal ratio, reversing which loans count as high-ratio.

---

### finance_016 — process_misinterpretation (medium)

**Intent**: Accounts with frequent negative-balance events

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Data-dictionary SQL
```sql
SELECT t.account_id,
COUNT(*) AS negative_balance_events
FROM trans t
WHERE t.balance < 0
GROUP BY t.account_id
HAVING COUNT(*) > 1
ORDER BY negative_balance_events DESC;
```

**D1 Verdict**: `partial`  **Notes**: Counts negative observations, but repeated observations can belong to one negative episode; frequency has no time basis.

---

### finance_021 — comparative_grounding (hard)

**Intent**: Loans that look risky despite having a good status.

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Data-dictionary SQL
```sql
SELECT l.loan_id,
l.account_id,
l.amount,
l.duration,
l.payments,
l.status
FROM loan l
JOIN account a
ON l.account_id = a.account_id
JOIN district d
ON a.district_id = d.district_id
WHERE l.status = 'good'
    AND (l.amount > 100000
    OR d.a12 > 10
    OR d.a13 > 10
    OR d.a15 > 1000
OR d.a16 > 1000) ;
```

**D1 Verdict**: `partial`  **Notes**: Combines good status with risk proxies, but lacks a within-status distributional comparison; status value needs verification.

---

### finance_022 — role_confusion (medium)

**Intent**: Loans with the most active repayment behavior

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Data-dictionary SQL
```sql
SELECT loan.loan_id,
loan.account_id,
loan.amount,
loan.duration,
loan.payments,
loan.status,
COUNT(trans.trans_id) AS transaction_count
FROM loan
JOIN trans
ON loan.account_id = trans.account_id
WHERE trans.type = 'debit'
AND trans.operation = 'credit in cash'
GROUP BY loan.loan_id,
loan.account_id,
loan.amount,
loan.duration,
loan.payments,
loan.status
ORDER BY transaction_count DESC
LIMIT 10;
```

**D1 Verdict**: `incorrect`  **Notes**: Combines debit transactions with a cash-credit operation and does not identify loan repayments.

---

### finance_023 — comparative_grounding (easy)

**Intent**: Find unusually small loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
status
FROM loan
WHERE amount < 1000;
```

**D1 Verdict**: `partial`  **Notes**: Correct comparative direction, but fixed amount cutoff.

---

### finance_024 — process_misinterpretation (hard)

**Intent**: Which accounts recovered from a negative balance?

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Data-dictionary SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2
ON t1.account_id = t2.account_id
WHERE t1.balance < 0
AND t2.balance >= 0
AND t1.date < t2.date;
```

**D1 Verdict**: `correct`  **Notes**: Finds a negative balance followed by a later nonnegative balance for the same account.

---

### finance_026 — comparative_grounding (medium)

**Intent**: Clients with high balance but low transaction volume

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
a.account_id,
AVG(t.balance) AS average_balance,
COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN account a
ON d.account_id = a.account_id
JOIN trans t
ON a.account_id = t.account_id
GROUP BY c.client_id,
c.gender,
c.birth_date,
a.account_id
    HAVING AVG(t.balance) >(
    SELECT AVG(balance)
FROM trans)
    AND COUNT(t.trans_id) <(
    SELECT AVG(transaction_count)
        FROM (
        SELECT COUNT(trans_id) AS transaction_count
        FROM trans
GROUP BY account_id) AS subquery)
ORDER BY average_balance DESC;
```

**D1 Verdict**: `partial`  **Notes**: Uses relative balance and transaction thresholds, but evaluates client-account pairs rather than aggregate clients and compares against mismatched populations.

---

### finance_027 — comparative_grounding (medium)

**Intent**: Find accounts with high net inflow

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT t.account_id,
SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS net_inflow
FROM trans t
GROUP BY t.account_id
HAVING SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) > 0
ORDER BY net_inflow DESC;
```

**D1 Verdict**: `partial`  **Notes**: Computes net inflow, but positive inflow is not necessarily unusually high inflow.

---

### finance_028 — role_confusion (easy)

**Intent**: Top clients by account_id

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### Data-dictionary SQL
```sql
SELECT disp.client_id,
COUNT(disp.account_id) AS account_count
FROM disp
GROUP BY disp.client_id
ORDER BY account_count DESC
LIMIT 10;
```

**D1 Verdict**: `correct`  **Notes**: Uses account counts rather than identifier magnitude, as permitted by the expected behavior.

---

### finance_030 — comparative_grounding (easy)

**Intent**: Find unusually large loans

**Expected behavior**: Use a distribution-based threshold for unusually large loans instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT loan_id,
account_id,
amount,
duration,
payments,
status
FROM loan
    WHERE amount >(
    SELECT AVG(amount) + 2 * STDDEV(amount)
FROM loan) ;
```

**D1 Verdict**: `correct`  **Notes**: Uses a distribution-based upper-tail loan-amount threshold.

---

### finance_031 — comparative_grounding (medium)

**Intent**: Find loans much larger than typical for their status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Data-dictionary SQL
```sql
    WITH avg_loan_amounts AS(
    SELECT status,
    AVG(amount) AS avg_amount
    FROM loan
GROUP BY status),
    large_loans AS(
    SELECT l.loan_id,
    l.account_id,
    l.amount,
    l.status
    FROM loan l
    JOIN avg_loan_amounts a
    ON l.status = a.status
WHERE l.amount > a.avg_amount * 1.5)
SELECT *
FROM large_loans;
```

**D1 Verdict**: `correct`  **Notes**: Compares each loan with its own status-group mean using a relative multiplier.

---

### finance_033 — comparative_grounding (hard)

**Intent**: Frequent small incoming transactions

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT account_id,
COUNT(*) AS transaction_count
FROM trans
WHERE type = 'credit'
AND amount < 1000
GROUP BY account_id
HAVING COUNT(*) > 10
ORDER BY transaction_count DESC;
```

**D1 Verdict**: `partial`  **Notes**: Captures repeated small credits, but both size and frequency cutoffs are fixed.

---

### finance_034 — quantitative_misinterpretation (easy)

**Intent**: Compare loan amounts and durations for different loan status

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Data-dictionary SQL
```sql
SELECT status,
AVG(amount) AS average_loan_amount,
AVG(duration) AS average_loan_duration
FROM loan
GROUP BY status;
```

**D1 Verdict**: `correct`  **Notes**: Compares average amount and duration by status, matching the intent. The generic ratio requirement is inconsistent with that intent.

---

### finance_035 — process_misinterpretation (medium)

**Intent**: Accounts frequently negative

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Data-dictionary SQL
```sql
SELECT account_id
FROM trans
GROUP BY account_id
HAVING SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) > 0;
```

**D1 Verdict**: `partial`  **Notes**: Identifies any negative observation, rather than frequent negative balances.

---

### finance_038 — quantitative_misinterpretation (medium)

**Intent**: Find total amount paid back for each loan

**Expected behavior**: Use the metric implied by the question, not a convenient proxy.

#### Data-dictionary SQL
```sql
SELECT loan.loan_id,
SUM(trans.amount) AS total_paid_back
FROM loan
JOIN trans
ON loan.account_id = trans.account_id
WHERE trans.type = 'credit'
GROUP BY loan.loan_id;
```

**D1 Verdict**: `partial`  **Notes**: Aggregates account credits, but does not establish that they are repayments attributable to each loan.

---

### finance_041 — process_misinterpretation (hard)

**Intent**: Find accounts showing sustained financial distress

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Data-dictionary SQL
```sql
SELECT a.account_id
FROM account a
JOIN trans t
ON a.account_id = t.account_id
GROUP BY a.account_id
HAVING SUM(CASE WHEN t.balance < 0 THEN 1 ELSE 0 END) > 3
AND AVG(t.balance) < 0;
```

**D1 Verdict**: `partial`  **Notes**: Uses repeated negative observations and negative average balance, but does not establish continuity or duration.

---

### finance_042 — comparative_grounding (medium)

**Intent**: Large loans per status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Data-dictionary SQL
```sql
SELECT status,
COUNT(*) AS large_loan_count
FROM loan
WHERE amount > 100000
GROUP BY status;
```

**D1 Verdict**: `partial`  **Notes**: Counts loans above a fixed threshold by status; does not identify relatively large loans within each status.

---

### finance_043 — process_misinterpretation (hard)

**Intent**: Which accounts stayed in negative balance for at least 30 days?

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Data-dictionary SQL
```sql
    WITH negative_balances AS(
    SELECT account_id,
    date,
    balance,
        LAG(date) OVER(PARTITION BY account_id
    ORDER BY date) AS prev_date,
        LAG(balance) OVER(PARTITION BY account_id
    ORDER BY date) AS prev_balance
    FROM trans
WHERE balance < 0),
    negative_periods AS(
    SELECT account_id,
    date AS start_date,
        LEAD(date) OVER(PARTITION BY account_id
    ORDER BY date) AS end_date
    FROM negative_balances
    WHERE prev_balance IS NULL
OR prev_balance >= 0),
    extended_negative_periods AS(
    SELECT account_id,
    start_date,
        COALESCE(end_date,
            (
            SELECT MAX(date)
            FROM trans
    WHERE account_id = nb.account_id)) AS end_date
FROM negative_periods nb)
SELECT DISTINCT account_id
FROM extended_negative_periods
WHERE (end_date::date - start_date::date) >= 30;
```

**D1 Verdict**: `partial`  **Notes**: Attempts duration modeling, but removes positive observations before detecting transitions, so inferred negative periods can span recoveries.

---

### finance_044 — process_misinterpretation (hard)

**Intent**: Customers with suspicious activity patterns

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Data-dictionary SQL
```sql
SELECT DISTINCT c.client_id,
c.gender,
c.birth_date,
d.a2 AS district_name
FROM client c
JOIN disp dp
ON c.client_id = dp.client_id
JOIN account a
ON dp.account_id = a.account_id
JOIN trans t
ON a.account_id = t.account_id
JOIN district d
ON c.district_id = d.district_id
WHERE t.amount > 10000
OR t.operation = 'withdrawal in cash'
ORDER BY c.client_id;
```

**D1 Verdict**: `incorrect`  **Notes**: Flags individual transactions using static conditions instead of identifying suspicious activity patterns.

---

### finance_046 — role_confusion (medium)

**Intent**: Heavy users

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN trans t
ON d.account_id = t.account_id
GROUP BY c.client_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**D1 Verdict**: `correct`  **Notes**: Transaction count is a meaningful operationalization of heavy usage.

---

### finance_047 — comparative_grounding (medium)

**Intent**: Clients with high repayment activity but low account balance

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT DISTINCT c.client_id,
c.gender,
c.birth_date,
a.account_id,
t.balance
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN account a
ON d.account_id = a.account_id
JOIN loan l
ON a.account_id = l.account_id
JOIN trans t
ON a.account_id = t.account_id
WHERE l.status = 'A' -- Assuming 'A' indicates active or high repayment activity
AND t.balance < 1000 -- Assuming low balance is defined as less than 1000
ORDER BY t.balance ASC;
```

**D1 Verdict**: `partial`  **Notes**: Captures low balance using a fixed cutoff, but static loan status does not measure repayment activity.

---

### finance_050 — comparative_grounding (medium)

**Intent**: Accounts with large balance and frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
a.district_id,
a.frequency,
a.date,
MAX(t.balance) AS max_balance,
COUNT(t.trans_id) AS withdrawal_count
FROM account a
JOIN trans t
ON a.account_id = t.account_id
WHERE t.type = 'debit'
AND t.operation = 'withdrawal'
GROUP BY a.account_id,
a.district_id,
a.frequency,
a.date
HAVING MAX(t.balance) > 10000
AND COUNT(t.trans_id) > 10
ORDER BY max_balance DESC;
```

**D1 Verdict**: `partial`  **Notes**: Measures balance and withdrawal count, but uses fixed thresholds and maximum historical balance.

---

### finance_051 — comparative_grounding (medium)

**Intent**: Clients with repeated small incoming transactions across multiple accounts

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Data-dictionary SQL
```sql
SELECT DISTINCT c.client_id,
c.gender,
c.birth_date
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN trans t
ON d.account_id = t.account_id
WHERE t.type = 'credit'
AND t.amount < 1000
GROUP BY c.client_id,
c.gender,
c.birth_date
HAVING COUNT(DISTINCT d.account_id) > 1
AND COUNT(t.trans_id) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Captures repeated credits across multiple accounts, but small uses a fixed cutoff.

---

### finance_053 — process_misinterpretation (hard)

**Intent**: Loans with rapidly worsening repayment behavior

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
SELECT loan.loan_id,
loan.account_id,
loan.amount,
loan.duration,
loan.payments,
loan.status
FROM loan
WHERE loan.status = 'B'
OR loan.status = 'D' ;
```

**D1 Verdict**: `incorrect`  **Notes**: Static loan status does not measure worsening repayment behavior.

---

### finance_055 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly volatile balances

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
SELECT account_id
    FROM (
    SELECT account_id,
    stddev(balance) AS balance_volatility
    FROM trans
GROUP BY account_id) AS account_volatility
ORDER BY balance_volatility DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Measures overall volatility, without checking whether volatility increases over time.

---

### finance_057 — process_misinterpretation (hard)

**Intent**: Accounts with recurring balance oscillation

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Data-dictionary SQL
```sql
SELECT account_id
    FROM (
    SELECT account_id,
        LAG(balance) OVER(PARTITION BY account_id
    ORDER BY date) AS prev_balance,
    balance
FROM trans) AS subquery
WHERE prev_balance IS NOT NULL
AND balance <> prev_balance
GROUP BY account_id
HAVING COUNT(DISTINCT balance) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Uses ordered balance changes, but does not require alternating directions or recurring oscillation.

---

### finance_058 — quantitative_misinterpretation (medium)

**Intent**: Clients with the highest loan repayment efficiency

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
l.loan_id,
l.amount,
l.duration,
l.payments,
(l.amount / l.duration) / l.payments AS repayment_efficiency
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN loan l
ON d.account_id = l.account_id
ORDER BY repayment_efficiency DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Computes a scheduled-payment ratio, but the intended efficiency definition is unspecified and no actual repayment performance is measured.

---

### finance_061 — quantitative_misinterpretation (hard)

**Intent**: Clients with unusually concentrated incoming cash flow

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
a.account_id,
SUM(t.amount) AS total_incoming
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN account a
ON d.account_id = a.account_id
JOIN trans t
ON a.account_id = t.account_id
WHERE t.type = 'credit'
GROUP BY c.client_id,
c.gender,
c.birth_date,
a.account_id
HAVING COUNT(DISTINCT t.date) < 3
ORDER BY total_incoming DESC;
```

**D1 Verdict**: `partial`  **Notes**: Uses few transaction dates as a concentration proxy, but omits the required concentration ratio and client-wide aggregation.

---

### finance_062 — process_misinterpretation (hard)

**Intent**: Which accounts show worsening balance patterns

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
SELECT account_id
    FROM (
    SELECT account_id,
        LAG(balance) OVER(PARTITION BY account_id
    ORDER BY date) AS previous_balance,
    balance
    FROM trans
    ORDER BY account_id,
date) AS subquery
WHERE balance < previous_balance
GROUP BY account_id
HAVING COUNT(*) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Detects multiple decreases, but not a consistent worsening pattern across consecutive periods.

---

### finance_065 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly delayed repayment activity

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
COUNT(l.loan_id) AS delayed_loans
FROM account a
JOIN loan l
ON a.account_id = l.account_id
WHERE l.status = 'D' -- Assuming 'D' indicates delayed repayment
GROUP BY a.account_id
ORDER BY delayed_loans DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Counts loans with a static status instead of measuring increasing repayment delays.

---

### finance_066 — process_misinterpretation (hard)

**Intent**: Accounts with recurring overdraft cycles

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Data-dictionary SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t
ON a.account_id = t.account_id
WHERE t.balance < 0
GROUP BY a.account_id
HAVING COUNT(CASE WHEN t.balance < 0 THEN 1 END) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Finds repeated negative observations, but not distinct overdraft-and-recovery cycles.

---

### finance_067 — process_misinterpretation (hard)

**Intent**: Clients whose transaction activity is accelerating

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN trans t
ON d.account_id = t.account_id
GROUP BY c.client_id,
c.gender,
c.birth_date
    HAVING COUNT(t.trans_id) >(
    SELECT AVG(transaction_count)
        FROM (
        SELECT COUNT(t2.trans_id) AS transaction_count
        FROM trans t2
        JOIN disp d2
        ON t2.account_id = d2.account_id
GROUP BY d2.client_id) AS subquery)
ORDER BY transaction_count DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Identifies above-average total activity, without measuring change or acceleration.

---

### finance_071 — comparative_grounding (hard)

**Intent**: Clients with unusually high debt-to-income ratios

**Expected behavior**: Compute each client's total outstanding loan amount divided by total credited transactions (as income proxy), then identify clients where this ratio is in the upper tail of the cross-client distribution — not clients exceeding a hardcoded threshold like 0.5 or 2.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
d.a11 AS average_salary,
SUM(l.amount) AS total_loan_amount,
    SUM(l.amount) / NULLIF(d.a11,
0) AS debt_to_income_ratio
FROM client c
JOIN disp dp
ON c.client_id = dp.client_id
JOIN account a
ON dp.account_id = a.account_id
JOIN loan l
ON a.account_id = l.account_id
JOIN district d
ON c.district_id = d.district_id
GROUP BY c.client_id,
c.gender,
c.birth_date,
d.a11
    HAVING SUM(l.amount) / NULLIF(d.a11,
0) > 1.0
ORDER BY debt_to_income_ratio DESC;
```

**D1 Verdict**: `partial`  **Notes**: Computes a related debt ratio, but uses district salary instead of credited income, original principal instead of outstanding debt, and a fixed cutoff.

---

### finance_072 — comparative_grounding (medium)

**Intent**: Accounts with unusually high overdraft frequency

**Expected behavior**: Count overdraft events (balance < 0) per account, then identify accounts in the upper tail of the overdraft-frequency distribution across all accounts, rather than accounts with more than N overdrafts.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
COUNT(t.trans_id) AS overdraft_count
FROM account a
JOIN trans t
ON a.account_id = t.account_id
WHERE t.balance < 0
GROUP BY a.account_id
    HAVING COUNT(t.trans_id) >(
    SELECT AVG(overdrafts)
        FROM (
        SELECT COUNT(t2.trans_id) AS overdrafts
        FROM trans t2
        WHERE t2.balance < 0
GROUP BY t2.account_id) AS subquery)
ORDER BY overdraft_count DESC;
```

**D1 Verdict**: `partial`  **Notes**: Uses a relative overdraft-count comparison, but excludes zero-overdraft accounts and uses the mean rather than an upper-tail criterion.

---

### finance_073 — comparative_grounding (hard)

**Intent**: Districts with outlier default rates

**Expected behavior**: Compute default rate per district (loans with status indicating default / total loans), identify districts in the upper tail of the cross-district default-rate distribution, not districts exceeding an arbitrary cutoff like 0.2 or 20%.

#### Data-dictionary SQL
```sql
SELECT d.district_id,
d.a2 AS district_name,
COUNT(l.loan_id) AS total_loans,
SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) AS defaulted_loans,
(SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) ::DECIMAL / COUNT(l.loan_id)) AS default_rate
FROM district d
JOIN account a
ON d.district_id = a.district_id
JOIN loan l
ON a.account_id = l.account_id
GROUP BY d.district_id,
d.a2
    HAVING (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) ::DECIMAL / COUNT(l.loan_id)) >(
    SELECT AVG(default_rate) + 2 * STDDEV(default_rate)
        FROM (
        SELECT (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) ::DECIMAL / COUNT(l.loan_id)) AS default_rate
        FROM district d
        JOIN account a
        ON d.district_id = a.district_id
        JOIN loan l
        ON a.account_id = l.account_id
GROUP BY d.district_id) AS subquery)
ORDER BY default_rate DESC;
```

**D1 Verdict**: `partial`  **Notes**: Correct district-rate and outlier structure, but 'default' is not established as a valid status mapping.

---

### finance_074 — process_misinterpretation (hard)

**Intent**: Accounts whose monthly transaction volume dropped sharply

**Expected behavior**: Compute monthly transaction counts per account, then identify accounts showing a consistent declining trend across at least three consecutive months, not accounts where any recent month is lower than any earlier month.

#### Data-dictionary SQL
```sql
    WITH monthly_volume AS(
    SELECT account_id,
        DATE_TRUNC('month',
            TO_DATE(date,
    'YYYY-MM-DD')) AS month,
    SUM(amount) AS total_volume
    FROM trans
    GROUP BY account_id,
        DATE_TRUNC('month',
            TO_DATE(date,
'YYYY-MM-DD'))),
    volume_change AS(
    SELECT account_id,
    month,
    total_volume,
        LAG(total_volume) OVER(PARTITION BY account_id
    ORDER BY month) AS previous_volume
FROM monthly_volume),
    sharp_drop AS(
    SELECT account_id,
    month,
    total_volume,
    previous_volume
    FROM volume_change
    WHERE previous_volume IS NOT NULL
AND total_volume < previous_volume * 0.5)
SELECT DISTINCT account_id
FROM sharp_drop;
```

**D1 Verdict**: `partial`  **Notes**: Detects a monthly amount decline, but requires transaction counts and declines across at least three consecutive months.

---

### finance_075 — process_misinterpretation (hard)

**Intent**: Clients whose credit card usage is accelerating

**Expected behavior**: Compute card transaction count per client per month, then identify clients where the month-over-month growth rate in transaction volume is consistently positive and increasing, not clients with the highest total card transaction count.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN card ca
ON d.disp_id = ca.disp_id
JOIN trans t
ON d.account_id = t.account_id
WHERE t.type = 'credit'
GROUP BY c.client_id,
c.gender,
c.birth_date
    HAVING COUNT(t.trans_id) >(
    SELECT AVG(transaction_count)
        FROM (
        SELECT COUNT(t2.trans_id) AS transaction_count
        FROM trans t2
        JOIN disp d2
        ON t2.account_id = d2.account_id
        JOIN card ca2
        ON d2.disp_id = ca2.disp_id
        WHERE t2.type = 'credit'
GROUP BY d2.client_id) AS subquery)
ORDER BY transaction_count DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Measures total credits for cardholding clients, without identifying card transactions or temporal acceleration.

---

### finance_076 — process_misinterpretation (hard)

**Intent**: Loans whose repayment pace is slowing

**Expected behavior**: Compute repayment amount per loan per month from transactions, then identify loans where the monthly repayment amount shows a consistent decline over time — a slowing pace — rather than loans with low total payments or a non-current status.

#### Data-dictionary SQL
```sql
SELECT loan.loan_id,
loan.account_id,
loan.amount,
loan.duration,
loan.payments,
loan.status
FROM loan
WHERE loan.status = 'B' -- Assuming 'B' indicates a slowing repayment pace
```

**D1 Verdict**: `incorrect`  **Notes**: Assumes static status indicates slowing repayment pace; no monthly repayment trend.

---

### finance_081 — role_confusion (hard)

**Intent**: Clients with highest financial dependency on loans

**Expected behavior**: Financial dependency should be measured by total outstanding loan amount relative to total account balance (a loan-to-assets ratio), not the raw number of loans. A client with one large loan may be more dependent than one with many small ones.

#### Data-dictionary SQL
```sql
SELECT c.client_id,
c.gender,
c.birth_date,
SUM(l.amount) AS total_loan_amount
FROM client c
JOIN disp d
ON c.client_id = d.client_id
JOIN loan l
ON d.account_id = l.account_id
GROUP BY c.client_id,
c.gender,
c.birth_date
ORDER BY total_loan_amount DESC
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Measures loan exposure, but omits outstanding-balance adjustments and the assets denominator.

---

### finance_082 — role_confusion (hard)

**Intent**: Most profitable districts for the bank

**Expected behavior**: Bank profitability per district should reflect revenue signals (loan amounts × duration as an interest income proxy) minus risk signals (default rates), not total transaction volume or client count, which conflates activity with value.

#### Data-dictionary SQL
```sql
SELECT d.district_id,
d.a2 AS district_name,
SUM(l.amount) AS total_loan_amount
FROM district d
JOIN account a
ON d.district_id = a.district_id
JOIN loan l
ON a.account_id = l.account_id
GROUP BY d.district_id,
d.a2
ORDER BY total_loan_amount DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Loan principal is a related revenue proxy, but duration and default risk are absent.

---

### finance_083 — role_confusion (hard)

**Intent**: Accounts with the most active savings behavior

**Expected behavior**: Savings behavior should reflect the net growth of account balance over time (consistent positive balance increments), not the total amount of credit transactions, which includes salary inflows and does not account for withdrawals.

#### Data-dictionary SQL
```sql
SELECT a.account_id,
COUNT(t.trans_id) AS transaction_count
FROM account a
JOIN trans t
ON a.account_id = t.account_id
WHERE t.type = 'credit'
AND t.operation = 'credit in cash'
GROUP BY a.account_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Counts incoming cash transactions, but does not measure net balance growth or consistency over time.

---

## Domain: public_safety

### public_safety_001 — comparative_grounding (easy)

**Intent**: Extremely severe crashes

**Expected behavior**: Identify crashes whose severity lies in the upper tail of the crash-severity distribution, using measures such as number of persons injured, number of persons killed, or combined severity indicators, rather than using a fixed constant like number_of_persons_injured > 10.

#### Data-dictionary SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0;
```

**D1 Verdict**: `partial`  **Notes**: Fatality presence is a severity signal, but no distribution-based extreme-severity criterion.

---

### public_safety_002 — comparative_grounding (medium)

**Intent**: Collisions with unusually high fatalities

**Expected behavior**: Identify collisions whose fatality counts lie in the upper tail of the fatality distribution (e.g., extreme outliers), rather than using fixed constants like number_of_persons_killed >= 5 or mixing injury thresholds with fatality-based intent.

#### Data-dictionary SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 5;
```

**D1 Verdict**: `partial`  **Notes**: Uses fatality count in the correct direction, but a fixed cutoff.

---

### public_safety_003 — quantitative_misinterpretation (medium)

**Intent**: Intersections with highest fatality rate

**Expected behavior**: Compute fatality rate per intersection as total fatalities divided by number of collisions (or appropriate exposure), and rank intersections by this rate rather than by total fatalities.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
cross_street_name,
SUM(number_of_persons_killed) AS total_fatalities,
COUNT(*) AS total_crashes,
SUM(number_of_persons_killed) ::FLOAT / COUNT(*) AS fatality_rate
FROM crashes
WHERE on_street_name IS NOT NULL
AND cross_street_name IS NOT NULL
GROUP BY on_street_name,
cross_street_name
HAVING COUNT(*) > 0
ORDER BY fatality_rate DESC
LIMIT 10;
```

**D1 Verdict**: `correct`  **Notes**: Computes fatalities per collision by intersection and ranks by the rate.

---

### public_safety_004 — process_misinterpretation (hard)

**Intent**: Areas where crash severity is worsening

**Expected behavior**: Identify areas where crash severity increases over time, such as rising injury/fatality severity across time windows, rather than ranking areas by total historical severity.

#### Data-dictionary SQL
```sql
SELECT borough,
SUM(number_of_persons_injured) AS total_injuries,
SUM(number_of_persons_killed) AS total_deaths
FROM crashes
GROUP BY borough
ORDER BY total_deaths DESC,
total_injuries DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Ranks historical severity totals without analyzing change over time.

---

### public_safety_008 — quantitative_misinterpretation (medium)

**Intent**: Areas where pedestrian injury risk is highest

**Expected behavior**: Compute pedestrian injury risk per area as a normalized measure (e.g., number of pedestrian injuries divided by number of collisions or probability of injury), and rank areas by this rate rather than raw counts.

#### Data-dictionary SQL
```sql
SELECT borough,
SUM(number_of_pedestrians_injured) AS total_pedestrian_injuries
FROM crashes
GROUP BY borough
ORDER BY total_pedestrian_injuries DESC
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Uses pedestrian injuries, but omits collision or exposure normalization.

---

### public_safety_010 — process_misinterpretation (medium)

**Intent**: Increasing collision trend over time

**Expected behavior**: Identify whether collision counts are increasing over time (e.g., rising trend across time windows such as months or years), rather than simply returning counts per date without analyzing the trend direction.

#### Data-dictionary SQL
```sql
SELECT crash_date,
COUNT(collision_id) AS total_collisions
FROM crashes
GROUP BY crash_date
ORDER BY crash_date;
```

**D1 Verdict**: `partial`  **Notes**: Produces a chronological count series, but does not evaluate trend direction.

---

### public_safety_011 — comparative_grounding (medium)

**Intent**: Vehicles involved in extreme-impact collisions

**Expected behavior**: Identify collisions whose impact (e.g., fatalities, injuries, or combined severity) lies in the upper tail of the severity distribution, and then extract associated vehicle types, rather than using fixed constants like number_of_persons_killed >= 5 or number_of_persons_injured >= 40.

#### Data-dictionary SQL
```sql
SELECT DISTINCT vehicle_type_code_1,
vehicle_type_code_2,
vehicle_type_code_3
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured > 10;
```

**D1 Verdict**: `partial`  **Notes**: Extracts vehicles from severe crashes, but uses fixed severity cutoffs.

---

### public_safety_016 — process_misinterpretation (medium)

**Intent**: Vehicle types with increasing crash involvement

**Expected behavior**: Identify vehicle types whose crash involvement increases over time (e.g., rising counts across time windows such as months or years), rather than simply counting total crashes per vehicle type and sorting.

#### Data-dictionary SQL
```sql
    WITH vehicle_crash_counts AS(
    SELECT vehicle_type_code_1 AS vehicle_type,
    COUNT(*) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_1 IS NOT NULL
    GROUP BY vehicle_type_code_1
    UNION ALL
    SELECT vehicle_type_code_2 AS vehicle_type,
    COUNT(*) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_2 IS NOT NULL
    GROUP BY vehicle_type_code_2
    UNION ALL
    SELECT vehicle_type_code_3 AS vehicle_type,
    COUNT(*) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_3 IS NOT NULL
GROUP BY vehicle_type_code_3),
    total_crash_counts AS(
    SELECT vehicle_type,
    SUM(crash_count) AS total_crashes
    FROM vehicle_crash_counts
GROUP BY vehicle_type)
SELECT vehicle_type,
total_crashes
FROM total_crash_counts
ORDER BY total_crashes ASC;
```

**D1 Verdict**: `incorrect`  **Notes**: Aggregates total involvement without a time dimension; ascending sorting does not identify increasing involvement.

---

### public_safety_018 — comparative_grounding (easy)

**Intent**: Collisions with unusually high injuries

**Expected behavior**: Identify collisions whose number of persons injured lies in the upper tail of the injury distribution (e.g., top quantile or statistical outliers), rather than using a fixed constant threshold.

#### Data-dictionary SQL
```sql
SELECT collision_id,
crash_date,
crash_time,
borough,
number_of_persons_injured
FROM crashes
    WHERE number_of_persons_injured >(
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured)
FROM crashes)
ORDER BY number_of_persons_injured DESC;
```

**D1 Verdict**: `correct`  **Notes**: Uses a distribution-based upper-tail injury threshold.

---

### public_safety_019 — comparative_grounding (medium)

**Intent**: Crashes with unusually high combined severity

**Expected behavior**: Compute a combined severity measure using injuries and fatalities, and identify crashes in the upper tail of this severity distribution (e.g., top quantile or outliers), rather than using a fixed constant threshold like > 10.

#### Data-dictionary SQL
```sql
SELECT collision_id,
crash_date,
crash_time,
borough,
zip_code,
number_of_persons_injured,
number_of_persons_killed
FROM crashes
    WHERE (number_of_persons_injured + number_of_persons_killed) >(
    SELECT AVG(number_of_persons_injured + number_of_persons_killed) + 2 * STDDEV(number_of_persons_injured + number_of_persons_killed)
FROM crashes)
ORDER BY (number_of_persons_injured + number_of_persons_killed) DESC;
```

**D1 Verdict**: `correct`  **Notes**: Computes combined severity and applies a distribution-based upper-tail threshold.

---

### public_safety_022 — process_misinterpretation (hard)

**Intent**: Find locations with sustained high injury collisions over time

**Expected behavior**: Identify locations where injury-related collisions remain consistently high over time (e.g., persistently high counts across multiple time windows or sustained upward trends), rather than filtering locations with more than a fixed number of injury collisions.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
cross_street_name,
COUNT(*) AS total_collisions,
SUM(number_of_persons_injured) AS total_injuries
FROM crashes
WHERE number_of_persons_injured > 0
GROUP BY on_street_name,
cross_street_name
HAVING COUNT(*) > 10
AND SUM(number_of_persons_injured) > 20
ORDER BY total_injuries DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Uses all-time count and injury thresholds without persistence across time windows.

---

### public_safety_027 — quantitative_misinterpretation (medium)

**Intent**: Find boroughs with high pedestrian injury rates

**Expected behavior**: Compute pedestrian injury rate per borough as the number of pedestrian injuries divided by the number of collisions, and identify boroughs with high rates rather than using total injury counts.

#### Data-dictionary SQL
```sql
SELECT borough,
SUM(number_of_pedestrians_injured) AS total_pedestrians_injured
FROM crashes
GROUP BY borough
HAVING SUM(number_of_pedestrians_injured) > 0
ORDER BY total_pedestrians_injured DESC;
```

**D1 Verdict**: `partial`  **Notes**: Ranks pedestrian injury totals rather than injuries per collision.

---

### public_safety_029 — process_misinterpretation (medium)

**Intent**: Locations with persistent crash patterns

**Expected behavior**: Identify locations where crashes persist over time, such as recurring crashes across multiple time windows or sustained patterns, rather than selecting locations with more than one crash overall.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
cross_street_name,
COUNT(*) AS crash_count
FROM crashes
GROUP BY on_street_name,
cross_street_name
HAVING COUNT(*) > 1
ORDER BY crash_count DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: More than one historical crash does not establish persistence across time windows.

---

### public_safety_031 — process_misinterpretation (hard)

**Intent**: Intersections with sustained high injury rates

**Expected behavior**: Identify intersections where injury rates remain consistently high over time (e.g., high injuries per collision across multiple time windows), rather than using a total injury count threshold.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
cross_street_name,
SUM(number_of_persons_injured) AS total_injuries
FROM crashes
WHERE on_street_name IS NOT NULL
AND cross_street_name IS NOT NULL
GROUP BY on_street_name,
cross_street_name
HAVING SUM(number_of_persons_injured) > 10
ORDER BY total_injuries DESC;
```

**D1 Verdict**: `incorrect`  **Notes**: Omits both injury-rate normalization and temporal persistence.

---

### public_safety_032 — process_misinterpretation (hard)

**Intent**: Find areas where commercial vehicles consistently account for the majority of severe collisions

**Expected behavior**: Identify areas where commercial vehicles account for the majority of severe collisions across multiple time windows, rather than only filtering commercial-vehicle collisions or counting them overall.

#### Data-dictionary SQL
```sql
SELECT borough,
zip_code,
COUNT(*) AS severe_collisions_count
FROM crashes
    WHERE (vehicle_type_code_1 LIKE '%COMMERCIAL%'
    OR vehicle_type_code_2 LIKE '%COMMERCIAL%'
OR vehicle_type_code_3 LIKE '%COMMERCIAL%')
    AND (number_of_persons_killed > 0
OR number_of_persons_injured > 5)
GROUP BY borough,
zip_code
    HAVING COUNT(*) >(
    SELECT COUNT(*)
    FROM crashes AS sub_crashes
    WHERE sub_crashes.borough = crashes.borough
    AND sub_crashes.zip_code = crashes.zip_code
        AND (sub_crashes.number_of_persons_killed > 0
OR sub_crashes.number_of_persons_injured > 5)) / 2
ORDER BY severe_collisions_count DESC;
```

**D1 Verdict**: `partial`  **Notes**: Checks commercial vehicles' majority share of severe crashes overall, but not consistently across time windows.

---

### public_safety_033 — comparative_grounding (easy)

**Intent**: Find severe crashes

**Expected behavior**: Identify crashes whose severity (e.g., based on injuries, fatalities, or combined severity measures) lies in the upper portion of the severity distribution, rather than using a fixed constant threshold.

#### Data-dictionary SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured > 5;
```

**D1 Verdict**: `partial`  **Notes**: Uses meaningful severity indicators, but fixed cutoffs.

---

### public_safety_037 — process_misinterpretation (hard)

**Intent**: Areas with worsening pedestrian injury trends

**Expected behavior**: Identify areas where pedestrian injuries increase over successive time windows, rather than ranking areas by aggregate injury counts.

#### Data-dictionary SQL
```sql
    WITH monthly_pedestrian_injuries AS(
        SELECT DATE_TRUNC('month',
            TO_DATE(crash_date,
    'YYYY-MM-DD')) AS month,
    borough,
    SUM(number_of_pedestrians_injured) AS total_pedestrian_injuries
    FROM crashes
    GROUP BY month,
borough),
    monthly_trends AS(
    SELECT month,
    borough,
    total_pedestrian_injuries,
        LAG(total_pedestrian_injuries) OVER(PARTITION BY borough
    ORDER BY month) AS previous_month_injuries
FROM monthly_pedestrian_injuries),
    worsening_trends AS(
    SELECT month,
    borough,
    total_pedestrian_injuries,
    previous_month_injuries
    FROM monthly_trends
WHERE total_pedestrian_injuries > previous_month_injuries)
SELECT borough,
COUNT(*) AS months_with_worsening_trends
FROM worsening_trends
GROUP BY borough
ORDER BY months_with_worsening_trends DESC;
```

**D1 Verdict**: `partial`  **Notes**: Detects monthly increases, but isolated increases can qualify without a sustained worsening trend.

---

### public_safety_038 — process_misinterpretation (hard)

**Intent**: Vehicle types with recurring severe crash involvement

**Expected behavior**: Identify vehicle types repeatedly involved in severe crashes across time periods, rather than ranking vehicle types using only total severe crash counts.

#### Data-dictionary SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
GROUP BY vehicle_type_code_1
HAVING COUNT(*) > 1
UNION
SELECT vehicle_type_code_2 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
GROUP BY vehicle_type_code_2
HAVING COUNT(*) > 1
UNION
SELECT vehicle_type_code_3 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
GROUP BY vehicle_type_code_3
HAVING COUNT(*) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Captures repeated severe involvement, but does not establish recurrence across distinct time periods.

---

### public_safety_040 — role_confusion (medium)

**Intent**: Areas with the most dangerous crash patterns

**Expected behavior**: Interpret danger using meaningful measures such as fatalities, injuries, or severity-weighted crash metrics, rather than ranking areas solely by collision frequency.

#### Data-dictionary SQL
```sql
SELECT borough,
zip_code,
SUM(number_of_persons_injured) AS total_injuries,
SUM(number_of_persons_killed) AS total_deaths,
COUNT(collision_id) AS total_crashes
FROM crashes
GROUP BY borough,
zip_code
ORDER BY total_deaths DESC,
total_injuries DESC,
total_crashes DESC
LIMIT 10;
```

**D1 Verdict**: `correct`  **Notes**: Uses fatalities and injuries to rank danger, as permitted by the expected behavior.

---

### public_safety_042 — comparative_grounding (medium)

**Intent**: Locations with unusually severe pedestrian crashes

**Expected behavior**: Identify pedestrian crashes whose severity lies in the upper tail of the pedestrian crash severity distribution and return the associated locations.

#### Data-dictionary SQL
```sql
SELECT borough,
on_street_name,
cross_street_name,
SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM crashes
GROUP BY borough,
on_street_name,
cross_street_name
HAVING SUM(number_of_pedestrians_injured) > 5
OR SUM(number_of_pedestrians_killed) > 0
ORDER BY total_pedestrians_killed DESC,
total_pedestrians_injured DESC;
```

**D1 Verdict**: `partial`  **Notes**: Uses pedestrian harm by location, but aggregates totals instead of selecting unusually severe individual pedestrian crashes.

---

### public_safety_046 — comparative_grounding (medium)

**Intent**: Time slots with unusually high crash frequency

**Expected behavior**: Aggregate crash counts by crash_time hour-of-day, then identify hours in the upper tail of the hour-level crash-count distribution, rather than flagging any hour with more than N crashes.

#### Data-dictionary SQL
```sql
SELECT crash_time,
COUNT(*) AS crash_count
FROM crashes
GROUP BY crash_time
ORDER BY crash_count DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Ranks crash counts, but does not extract hour-of-day or apply a distributional upper-tail criterion.

---

### public_safety_047 — comparative_grounding (medium)

**Intent**: Vehicle types involved in unusually severe crashes

**Expected behavior**: Compute average severity (persons injured + killed) per crash by vehicle type, then identify vehicle types where this severity measure is in the upper tail of the cross-vehicle-type distribution, not those exceeding a fixed injury threshold.

#### Data-dictionary SQL
```sql
SELECT DISTINCT vehicle_type_code_1 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured > 5
UNION
SELECT DISTINCT vehicle_type_code_2 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured > 5
UNION
SELECT DISTINCT vehicle_type_code_3 AS vehicle_type
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured > 5;
```

**D1 Verdict**: `partial`  **Notes**: Finds types appearing in severe crashes, but omits average severity by type and the cross-type distribution.

---

### public_safety_048 — comparative_grounding (easy)

**Intent**: ZIP codes with outlier crash densities

**Expected behavior**: Count crashes per zip_code and identify ZIP codes in the upper tail of the crash-count distribution across all ZIP codes, not ZIP codes exceeding a hardcoded threshold.

#### Data-dictionary SQL
```sql
    WITH crash_counts AS(
    SELECT zip_code,
    COUNT(*) AS crash_count
    FROM crashes
    WHERE zip_code IS NOT NULL
GROUP BY zip_code),
    stats AS(
    SELECT AVG(crash_count) AS avg_crash_count,
    STDDEV(crash_count) AS stddev_crash_count
FROM crash_counts)
SELECT cc.zip_code,
cc.crash_count
FROM crash_counts cc
JOIN stats s
ON 1=1
WHERE cc.crash_count > s.avg_crash_count + 2 * s.stddev_crash_count
OR cc.crash_count < s.avg_crash_count - 2 * s.stddev_crash_count;
```

**D1 Verdict**: `partial`  **Notes**: Correct count-distribution structure, but includes lower-tail ZIP codes when only the upper tail is required.

---

### public_safety_049 — comparative_grounding (hard)

**Intent**: Hours of day with unusually high pedestrian fatality risk

**Expected behavior**: Compute pedestrian fatality rate per hour (pedestrian killed / crashes in that hour) and identify hours in the upper tail of this rate distribution, not hours with fatalities exceeding a fixed count or falling in a manually specified time window.

#### Data-dictionary SQL
```sql
SELECT crash_time,
SUM(number_of_pedestrians_killed) AS total_pedestrian_fatalities
FROM crashes
GROUP BY crash_time
    HAVING SUM(number_of_pedestrians_killed) >(
    SELECT AVG(total_pedestrian_fatalities)
        FROM (
        SELECT SUM(number_of_pedestrians_killed) AS total_pedestrian_fatalities
        FROM crashes
GROUP BY crash_time) AS subquery)
ORDER BY total_pedestrian_fatalities DESC;
```

**D1 Verdict**: `partial`  **Notes**: Compares fatality totals, but omits the per-crash denominator, hour extraction, and upper-tail criterion.

---

### public_safety_050 — process_misinterpretation (hard)

**Intent**: Streets with persistently recurring severe crashes across years

**Expected behavior**: Identify streets (on_street_name) that appear in the upper severity tier in multiple distinct years — demonstrating structural danger, not just a one-time spike — rather than streets with the highest all-time aggregate crash count.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
COUNT(collision_id) AS severe_crash_count
FROM crashes
WHERE number_of_persons_killed > 0
OR number_of_persons_injured >= 5
GROUP BY on_street_name
        HAVING COUNT(DISTINCT EXTRACT(YEAR
            FROM TO_DATE(crash_date,
'YYYY-MM-DD'))) > 1
ORDER BY severe_crash_count DESC;
```

**D1 Verdict**: `partial`  **Notes**: Requires severe crashes in multiple years, but not upper-tier street severity within each year.

---

### public_safety_051 — process_misinterpretation (hard)

**Intent**: Boroughs with accelerating cyclist injury rates

**Expected behavior**: Compute cyclist injury rate (cyclists injured per crash) per borough per year, then identify boroughs where this rate is consistently increasing across multiple consecutive years, not boroughs with the highest total cyclist injury count.

#### Data-dictionary SQL
```sql
    WITH monthly_cyclist_injuries AS(
    SELECT borough,
        DATE_TRUNC('month',
            TO_DATE(crash_date,
    'YYYY-MM-DD')) AS month,
    SUM(number_of_cyclist_injured) AS total_cyclist_injuries
    FROM crashes
    WHERE borough IS NOT NULL
    GROUP BY borough,
        DATE_TRUNC('month',
            TO_DATE(crash_date,
'YYYY-MM-DD'))),
    monthly_injury_growth AS(
    SELECT borough,
    month,
    total_cyclist_injuries,
        LAG(total_cyclist_injuries) OVER(PARTITION BY borough
    ORDER BY month) AS previous_month_injuries
FROM monthly_cyclist_injuries),
    accelerating_boroughs AS(
    SELECT borough,
    COUNT(*) AS accelerating_months
    FROM monthly_injury_growth
    WHERE total_cyclist_injuries > previous_month_injuries
GROUP BY borough)
SELECT borough
FROM accelerating_boroughs
WHERE accelerating_months > 0
ORDER BY accelerating_months DESC;
```

**D1 Verdict**: `partial`  **Notes**: Detects monthly injury-count increases, but omits annual rates and consistent increases across consecutive years.

---

### public_safety_052 — process_misinterpretation (hard)

**Intent**: Contributing factors with increasing crash prevalence over time

**Expected behavior**: Compute the share of crashes attributed to each contributing factor per year, and identify factors where this share consistently increases across multiple years, not factors with the highest total occurrence count.

#### Data-dictionary SQL
```sql
    WITH monthly_crashes AS(
        SELECT DATE_TRUNC('month',
            TO_DATE(crash_date,
    'YYYY-MM-DD')) AS crash_month,
    contributing_factor_vehicle_1 AS contributing_factor
    FROM crashes
    UNION ALL
        SELECT DATE_TRUNC('month',
            TO_DATE(crash_date,
    'YYYY-MM-DD')) AS crash_month,
    contributing_factor_vehicle_2 AS contributing_factor
    FROM crashes
    UNION ALL
        SELECT DATE_TRUNC('month',
            TO_DATE(crash_date,
    'YYYY-MM-DD')) AS crash_month,
    contributing_factor_vehicle_3 AS contributing_factor
FROM crashes),
    factor_monthly_counts AS(
    SELECT crash_month,
    contributing_factor,
    COUNT(*) AS crash_count
    FROM monthly_crashes
    WHERE contributing_factor IS NOT NULL
    GROUP BY crash_month,
contributing_factor),
    factor_trend AS(
    SELECT contributing_factor,
        ARRAY_AGG(crash_count
    ORDER BY crash_month) AS monthly_counts
    FROM factor_monthly_counts
GROUP BY contributing_factor)
SELECT contributing_factor
FROM factor_trend
WHERE monthly_counts = ARRAY_SORT(monthly_counts)
    AND ARRAY_LENGTH(monthly_counts,
1) > 1;
```

**D1 Verdict**: `partial`  **Notes**: Attempts a nondecreasing count trend, but omits annual crash shares, allows flat counts, and may double-count crashes across factor slots.

---

### public_safety_053 — quantitative_misinterpretation (medium)

**Intent**: Vehicle types with highest injury rate per crash involvement

**Expected behavior**: Compute average total persons injured per crash for crashes involving each vehicle type, then rank vehicle types by this per-crash rate, not by the raw total injury count across all crashes involving that type.

#### Data-dictionary SQL
```sql
    WITH vehicle_involvement AS(
    SELECT vehicle_type_code_1 AS vehicle_type,
    number_of_persons_injured
    FROM crashes
    WHERE vehicle_type_code_1 IS NOT NULL
    UNION ALL
    SELECT vehicle_type_code_2 AS vehicle_type,
    number_of_persons_injured
    FROM crashes
    WHERE vehicle_type_code_2 IS NOT NULL
    UNION ALL
    SELECT vehicle_type_code_3 AS vehicle_type,
    number_of_persons_injured
    FROM crashes
WHERE vehicle_type_code_3 IS NOT NULL),
    injury_rate AS(
    SELECT vehicle_type,
    SUM(number_of_persons_injured) AS total_injuries,
    COUNT(*) AS involvement_count,
    SUM(number_of_persons_injured) * 1.0 / COUNT(*) AS injury_rate
    FROM vehicle_involvement
GROUP BY vehicle_type)
SELECT vehicle_type,
injury_rate
FROM injury_rate
ORDER BY injury_rate DESC
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Computes injuries per vehicle-slot involvement, but repeated appearances of the same type in one crash can distort the required per-crash rate.

---

### public_safety_054 — quantitative_misinterpretation (medium)

**Intent**: Contributing factors with highest lethality ratio

**Expected behavior**: Compute the lethality ratio as number_of_persons_killed / (number_of_persons_killed + number_of_persons_injured) per contributing factor, then rank by this ratio. Factors in fewer but more lethal crashes would otherwise be obscured by high-frequency low-lethality ones.

#### Data-dictionary SQL
```sql
SELECT contributing_factor,
SUM(number_of_persons_killed) AS total_killed,
SUM(number_of_persons_injured) AS total_injured,
CASE WHEN SUM(number_of_persons_injured) = 0 THEN NULL ELSE SUM(number_of_persons_killed) ::FLOAT / SUM(number_of_persons_injured) END AS lethality_ratio
    FROM (
    SELECT contributing_factor_vehicle_1 AS contributing_factor,
    number_of_persons_killed,
    number_of_persons_injured
    FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_2 AS contributing_factor,
    number_of_persons_killed,
    number_of_persons_injured
    FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_3 AS contributing_factor,
    number_of_persons_killed,
    number_of_persons_injured
FROM crashes) AS factors
WHERE contributing_factor IS NOT NULL
GROUP BY contributing_factor
ORDER BY lethality_ratio DESC NULLS LAST
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Uses killed/injured rather than killed/(killed + injured); excludes fatal-only groups and may duplicate crashes across factor slots.

---

### public_safety_055 — quantitative_misinterpretation (medium)

**Intent**: Time slots with highest pedestrian-to-motorist injury ratio

**Expected behavior**: Compute the ratio of total pedestrian injuries to total motorist injuries per hour of day, and rank hours by this ratio to identify when pedestrians bear a disproportionate share of injury risk relative to motorists.

#### Data-dictionary SQL
```sql
SELECT crash_time,
SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
SUM(number_of_motorist_injured) AS total_motorists_injured,
CASE WHEN SUM(number_of_motorist_injured) = 0 THEN NULL ELSE SUM(number_of_pedestrians_injured) ::FLOAT / SUM(number_of_motorist_injured) END AS pedestrian_to_motorist_injury_ratio
FROM crashes
GROUP BY crash_time
ORDER BY pedestrian_to_motorist_injury_ratio DESC NULLS LAST
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Correct injury ratio, but groups by raw time rather than hour-of-day.

---

### public_safety_060 — role_confusion (medium)

**Intent**: Boroughs with worst pedestrian safety record

**Expected behavior**: Pedestrian safety should be measured by pedestrian injuries per crash (or per unit of exposure), not total pedestrian injury count. Boroughs with more crashes would otherwise rank worst purely because of volume, masking genuine rate differences.

#### Data-dictionary SQL
```sql
SELECT borough,
SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM crashes
GROUP BY borough
ORDER BY total_pedestrians_killed DESC,
total_pedestrians_injured DESC;
```

**D1 Verdict**: `partial`  **Notes**: Uses pedestrian harm totals, but omits per-crash or exposure normalization.

---

### public_safety_061 — role_confusion (medium)

**Intent**: Streets with most dangerous conditions

**Expected behavior**: Street danger should reflect injury or fatality rate per crash on that street, not raw collision count. A busy intersection with many low-severity crashes is less dangerous than one with fewer but consistently severe crashes.

#### Data-dictionary SQL
```sql
SELECT on_street_name,
SUM(number_of_persons_injured + number_of_persons_killed) AS total_casualties
FROM crashes
GROUP BY on_street_name
ORDER BY total_casualties DESC
LIMIT 10;
```

**D1 Verdict**: `partial`  **Notes**: Uses street casualty totals, but omits the collision denominator.

---

### public_safety_062 — role_confusion (medium)

**Intent**: Vehicle types most responsible for cyclist injuries

**Expected behavior**: Responsibility for cyclist injuries should be measured by the average number of cyclists injured per crash where the vehicle type appears, not the total number of crashes or total cyclist injuries — common vehicle types would otherwise dominate by volume.

#### Data-dictionary SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type,
SUM(number_of_cyclist_injured) AS total_cyclist_injuries
FROM crashes
GROUP BY vehicle_type_code_1
ORDER BY total_cyclist_injuries DESC
LIMIT 1;
```

**D1 Verdict**: `partial`  **Notes**: Uses cyclist injury totals from only the first vehicle slot, without per-crash normalization.

---
