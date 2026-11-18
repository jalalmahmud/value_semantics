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

Total cases: 124

**Verdict options**: `correct` / `partial` / `incorrect`

---

## Domain: finance

### finance_001 — comparative_grounding (medium)

**Intent**: Loans with unusually high principal amount given their loan status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, amount, status
FROM loan
WHERE amount > 439769
ORDER BY status, amount DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE amount > (
    SELECT AVG(amount) + 2 * STDDEV(amount)
    FROM loan
    WHERE loan.status = loan.status
)
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### finance_002 — comparative_grounding (easy)

**Intent**: Find unusually large withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT trans_id, account_id, date, amount
FROM trans
WHERE type = 'withdrawal' AND amount > 20740
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT trans_id, account_id, date, type, operation, amount, balance, k_symbol, bank, account
FROM trans
WHERE type = 'withdrawal' AND amount > (
    SELECT AVG(amount) + 2 * STDDEV(amount)
    FROM trans
    WHERE type = 'withdrawal'
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_003 — process_misinterpretation (medium)

**Intent**: Accounts with sustained negative balance

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.balance < 0
GROUP BY a.account_id
HAVING COUNT(DISTINCT t.date) > 1
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH negative_balances AS (
    SELECT account_id, date, balance,
           LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS prev_balance
    FROM trans
),
sustained_negative AS (
    SELECT account_id
    FROM negative_balances
    WHERE balance < 0 AND prev_balance < 0
    GROUP BY account_id
)
SELECT DISTINCT account_id
FROM sustained_negative;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_004 — comparative_grounding (easy)

**Intent**: Find large loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount > 439769;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount > 100000; -- Assuming "large loans" are those with an amount greater than 100,000
```

**Planner Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

---

### finance_005 — comparative_grounding (medium)

**Intent**: Accounts with unusually frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT 
    a.account_id, 
    COUNT(t.trans_id) AS withdrawal_count
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'withdrawal'
GROUP BY 
    a.account_id
HAVING 
    COUNT(t.trans_id) > (
        SELECT 
            AVG(withdrawal_count) + 2 * STDDEV(withdrawal_count)
        FROM (
            SELECT 
                COUNT(t2.trans_id) AS withdrawal_count
            FROM 
                trans t2
            WHERE 
                t2.type = 'withdrawal'
            GROUP BY 
                t2.account_id
        ) AS subquery
    )
ORDER BY 
    withdrawal_count DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT account_id
FROM trans
WHERE type = 'withdrawal'
GROUP BY account_id
HAVING COUNT(trans_id) > (
    SELECT AVG(withdrawal_count) + 2 * STDDEV(withdrawal_count)
    FROM (
        SELECT COUNT(trans_id) AS withdrawal_count
        FROM trans
        WHERE type = 'withdrawal'
        GROUP BY account_id
    ) AS subquery
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_006 — role_confusion (hard)

**Intent**: Clients with highest account

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, COUNT(d.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 1;
```

**PM Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

#### Planner-enforced SQL
```sql
SELECT c.client_id, COUNT(d.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 1;
```

**Planner Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

---

### finance_008 — process_misinterpretation (hard)

**Intent**: Loans with payment irregularity

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Prompt-mediated SQL
```sql
SELECT loan.loan_id, loan.account_id, loan.amount, loan.duration, loan.payments, loan.status
FROM loan
WHERE loan.status = 'B' OR loan.status = 'D';
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
SELECT l.loan_id, l.account_id, l.amount, l.duration, l.payments, l.status
FROM loan l
WHERE l.status = 'B' OR l.status = 'D';
```

**Planner Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

---

### finance_009 — comparative_grounding (medium)

**Intent**: Loans with high amount but low repayment

**Expected behavior**: Use relative high/low cutoffs for both amount and repayment.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, amount, payments, duration, status
FROM loan
WHERE amount > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM loan)
  AND payments < (SELECT PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY payments) FROM loan);
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount > (SELECT AVG(amount) + 2 * STDDEV(amount) FROM loan)
  AND payments < (SELECT AVG(payments) - 2 * STDDEV(payments) FROM loan);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_010 — quantitative_misinterpretation (medium)

**Intent**: Loans with largest remaining balance

**Expected behavior**: Rank by estimated unpaid balance, not by original loan amount.

#### Prompt-mediated SQL
```sql
SELECT 
    l.loan_id, 
    l.account_id, 
    l.amount - (l.payments * l.duration) AS remaining_balance
FROM 
    loan l
ORDER BY 
    remaining_balance DESC
LIMIT 10;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT 
    l.loan_id, 
    l.account_id, 
    l.amount - COALESCE(SUM(t.amount), 0) AS remaining_balance
FROM 
    loan l
LEFT JOIN 
    trans t ON l.account_id = t.account_id AND t.type = 'debit'
GROUP BY 
    l.loan_id, l.account_id, l.amount
ORDER BY 
    remaining_balance DESC
LIMIT 1;
```

**Planner Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

---

### finance_011 — role_confusion (medium)

**Intent**: Most important accounts

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Prompt-mediated SQL
```sql
SELECT 
    a.account_id, 
    SUM(t.amount) AS total_transaction_amount
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
GROUP BY 
    a.account_id
ORDER BY 
    total_transaction_amount DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT account_id, COUNT(trans_id) AS transaction_count
FROM trans
GROUP BY account_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### finance_012 — process_misinterpretation (hard)

**Intent**: Accounts with increasing withdrawal frequency over time

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
WITH withdrawal_counts AS (
    SELECT 
        a.account_id,
        t.date,
        COUNT(*) FILTER (WHERE t.type = 'withdrawal') AS withdrawal_count
    FROM 
        account a
    JOIN 
        trans t ON a.account_id = t.account_id
    GROUP BY 
        a.account_id, t.date
),
withdrawal_trend AS (
    SELECT 
        account_id,
        withdrawal_count,
        LAG(withdrawal_count) OVER (PARTITION BY account_id ORDER BY date) AS previous_withdrawal_count
    FROM 
        withdrawal_counts
)
SELECT DISTINCT 
    account_id
FROM 
    withdrawal_trend
WHERE 
    withdrawal_count > previous_withdrawal_count
ORDER BY 
    account_id;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH withdrawal_trans AS (
    SELECT 
        account_id, 
        date, 
        amount,
        ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY date) as rn
    FROM trans
    WHERE type = 'withdrawal'
),
withdrawal_counts AS (
    SELECT 
        account_id, 
        COUNT(*) as withdrawal_count
    FROM withdrawal_trans
    GROUP BY account_id
),
withdrawal_increase AS (
    SELECT 
        wt1.account_id
    FROM withdrawal_trans wt1
    JOIN withdrawal_trans wt2 
    ON wt1.account_id = wt2.account_id 
    AND wt1.rn = wt2.rn - 1
    WHERE wt2.amount > wt1.amount
    GROUP BY wt1.account_id
    HAVING COUNT(*) = (SELECT COUNT(*) FROM withdrawal_trans wt3 WHERE wt3.account_id = wt1.account_id) - 1
)
SELECT DISTINCT account_id
FROM withdrawal_increase
```

**Planner Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

---

### finance_014 — comparative_grounding (hard)

**Intent**: Loans with extreme duration compared to principal

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE duration > 60 AND amount < 439769;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE duration > (SELECT AVG(duration) + 2 * STDDEV(duration) FROM loan)
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### finance_015 — quantitative_misinterpretation (medium)

**Intent**: Loans with high repayment ratio

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Prompt-mediated SQL
```sql
SELECT 
    loan.loan_id, 
    loan.account_id, 
    loan.amount, 
    loan.payments, 
    (loan.payments * loan.duration) / loan.amount AS repayment_ratio
FROM 
    loan
WHERE 
    (loan.payments * loan.duration) / loan.amount > 1
ORDER BY 
    repayment_ratio DESC;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT loan.loan_id, loan.account_id, loan.amount, loan.payments, (loan.payments * loan.duration) / loan.amount AS repayment_ratio
FROM loan
WHERE (loan.payments * loan.duration) / loan.amount > 1
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### finance_016 — process_misinterpretation (medium)

**Intent**: Accounts with frequent negative-balance events

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Prompt-mediated SQL
```sql
SELECT 
    a.account_id
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.balance < 0
GROUP BY 
    a.account_id
HAVING 
    COUNT(CASE WHEN t.balance < 0 THEN 1 END) > 1
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
SELECT a.account_id, COUNT(t.trans_id) AS negative_balance_events
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.balance < 0
GROUP BY a.account_id
HAVING COUNT(t.trans_id) > 1
ORDER BY negative_balance_events DESC;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_021 — comparative_grounding (hard)

**Intent**: Loans that look risky despite having a good status.

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Prompt-mediated SQL
```sql
SELECT loan.loan_id, loan.account_id, loan.amount, loan.duration, loan.payments, loan.status
FROM loan
WHERE loan.status = 'good' AND loan.amount > (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM loan
);
```

**PM Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE status = 'good' AND amount > (SELECT AVG(amount) + 2 * STDDEV(amount) FROM loan)
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### finance_022 — role_confusion (medium)

**Intent**: Loans with the most active repayment behavior

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Prompt-mediated SQL
```sql
SELECT 
    l.loan_id, 
    l.account_id, 
    l.amount, 
    l.duration, 
    l.payments, 
    l.status, 
    COUNT(t.trans_id) AS transaction_count
FROM 
    loan l
JOIN 
    trans t ON l.account_id = t.account_id
WHERE 
    t.type = 'credit'
GROUP BY 
    l.loan_id, l.account_id, l.amount, l.duration, l.payments, l.status
ORDER BY 
    transaction_count DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT l.loan_id, l.account_id, COUNT(t.trans_id) AS transaction_count
FROM loan l
JOIN trans t ON l.account_id = t.account_id
WHERE t.type = 'credit'
GROUP BY l.loan_id, l.account_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### finance_023 — comparative_grounding (easy)

**Intent**: Find unusually small loans

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, amount, date
FROM loan
WHERE amount < (SELECT PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY amount) FROM loan)
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, amount, duration, payments, status
FROM loan
WHERE amount < (SELECT AVG(amount) - 2 * STDDEV(amount) FROM loan);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_024 — process_misinterpretation (hard)

**Intent**: Which accounts recovered from a negative balance?

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2 ON t1.account_id = t2.account_id
WHERE t1.balance < 0 AND t2.balance >= 0 AND t1.date < t2.date;
```

**PM Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

#### Planner-enforced SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2 ON t1.account_id = t2.account_id
WHERE t1.balance < 0 AND t2.balance >= 0 AND t1.date < t2.date;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_026 — comparative_grounding (medium)

**Intent**: Clients with high balance but low transaction volume

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT 
    c.client_id, 
    c.gender, 
    c.birth_date, 
    AVG(t.balance) AS average_balance, 
    COUNT(t.trans_id) AS transaction_count
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    account a ON d.account_id = a.account_id
JOIN 
    trans t ON a.account_id = t.account_id
GROUP BY 
    c.client_id, c.gender, c.birth_date
HAVING 
    AVG(t.balance) > 58647 AND COUNT(t.trans_id) < 10
ORDER BY 
    average_balance DESC, transaction_count ASC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, t.balance, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
GROUP BY c.client_id, c.gender, c.birth_date, t.balance
HAVING t.balance > (SELECT AVG(balance) + 2 * STDDEV(balance) FROM trans)
   AND COUNT(t.trans_id) < (SELECT AVG(transaction_count) FROM (
       SELECT COUNT(trans_id) AS transaction_count
       FROM trans
       GROUP BY account_id
   ) AS subquery)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_027 — comparative_grounding (medium)

**Intent**: Find accounts with high net inflow

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT 
    t.account_id, 
    SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
    SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS net_inflow
FROM 
    trans t
GROUP BY 
    t.account_id
HAVING 
    SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
    SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) > 0
ORDER BY 
    net_inflow DESC;
```

**PM Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

#### Planner-enforced SQL
```sql
SELECT t.account_id, SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
       SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) AS net_inflow
FROM trans t
GROUP BY t.account_id
HAVING SUM(CASE WHEN t.type = 'credit' THEN t.amount ELSE 0 END) - 
       SUM(CASE WHEN t.type = 'debit' THEN t.amount ELSE 0 END) > 0
ORDER BY net_inflow DESC;
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### finance_028 — role_confusion (easy)

**Intent**: Top clients by account_id

**Expected behavior**: Do not rank by IDs; ask for clarification or count related accounts if that is intended.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, COUNT(d.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 10;
```

**PM Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

#### Planner-enforced SQL
```sql
SELECT c.client_id, COUNT(d.account_id) AS account_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
GROUP BY c.client_id
ORDER BY account_count DESC
LIMIT 10;
```

**Planner Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

---

### finance_030 — comparative_grounding (easy)

**Intent**: Find unusually large loans

**Expected behavior**: Use a distribution-based threshold for unusually large loans instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE amount > 439769;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE amount > (SELECT AVG(amount) + 2 * STDDEV(amount) FROM loan);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_031 — comparative_grounding (medium)

**Intent**: Find loans much larger than typical for their status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Prompt-mediated SQL
```sql
SELECT 
    loan_id, 
    account_id, 
    amount, 
    status
FROM 
    loan
WHERE 
    amount > (
        SELECT 
            PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) 
        FROM 
            loan AS l2 
        WHERE 
            l2.status = loan.status
    )
ORDER BY 
    status, 
    amount DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE amount > (
    SELECT AVG(amount) + 2 * STDDEV(amount)
    FROM loan
    WHERE loan.status = loan.status
);
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### finance_033 — comparative_grounding (hard)

**Intent**: Frequent small incoming transactions

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT 
    account_id, 
    COUNT(*) AS transaction_count, 
    AVG(amount) AS average_amount
FROM 
    trans
WHERE 
    type = 'credit' AND 
    amount < 1000
GROUP BY 
    account_id
HAVING 
    COUNT(*) > 10
ORDER BY 
    transaction_count DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT trans.account_id, COUNT(trans.trans_id) AS transaction_count
FROM trans
WHERE trans.type = 'credit' AND trans.amount < 1000
GROUP BY trans.account_id
HAVING COUNT(trans.trans_id) > 10
ORDER BY transaction_count DESC;
```

**Planner Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

---

### finance_034 — quantitative_misinterpretation (easy)

**Intent**: Compare loan amounts and durations for different loan status

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Prompt-mediated SQL
```sql
SELECT 
    status,
    AVG(amount) AS average_loan_amount,
    AVG(duration) AS average_loan_duration
FROM 
    loan
GROUP BY 
    status;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT 
    status, 
    AVG(amount) AS average_amount, 
    AVG(duration) AS average_duration
FROM 
    loan
GROUP BY 
    status;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### finance_035 — process_misinterpretation (medium)

**Intent**: Accounts frequently negative

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Prompt-mediated SQL
```sql
SELECT account.account_id
FROM account
JOIN trans ON account.account_id = trans.account_id
GROUP BY account.account_id
HAVING SUM(CASE WHEN trans.balance < 0 THEN 1 ELSE 0 END) > 0.5 * COUNT(trans.trans_id)
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
SELECT account_id, COUNT(*) AS negative_balance_count
FROM trans
WHERE balance < 0
GROUP BY account_id
HAVING COUNT(*) > 0
ORDER BY negative_balance_count DESC;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_038 — quantitative_misinterpretation (medium)

**Intent**: Find total amount paid back for each loan

**Expected behavior**: Use the metric implied by the question, not a convenient proxy.

#### Prompt-mediated SQL
```sql
SELECT 
    loan.loan_id, 
    SUM(trans.amount) AS total_paid_back
FROM 
    loan
JOIN 
    trans ON loan.account_id = trans.account_id
WHERE 
    trans.type = 'credit'
GROUP BY 
    loan.loan_id;
```

**PM Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

#### Planner-enforced SQL
```sql
SELECT 
    loan.loan_id, 
    SUM(trans.amount) AS total_paid_back
FROM 
    loan
JOIN 
    trans ON loan.account_id = trans.account_id
WHERE 
    trans.type = 'credit'
GROUP BY 
    loan.loan_id;
```

**Planner Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

---

### finance_041 — process_misinterpretation (hard)

**Intent**: Find accounts showing sustained financial distress

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Prompt-mediated SQL
```sql
SELECT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
GROUP BY a.account_id
HAVING AVG(t.balance) < 58647
```

**PM Verdict**: `partial`  **Notes**: Captures a related distress/duration/delay signal but does not fully model the required process pattern.

#### Planner-enforced SQL
```sql
WITH account_balance_changes AS (
    SELECT 
        account_id, 
        date, 
        balance,
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM trans
),
financial_distress AS (
    SELECT 
        account_id
    FROM 
        account_balance_changes
    WHERE 
        balance < previous_balance
    GROUP BY 
        account_id
    HAVING 
        COUNT(*) >= 3
)
SELECT 
    a.account_id
FROM 
    account a
JOIN 
    financial_distress fd ON a.account_id = fd.account_id;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_042 — comparative_grounding (medium)

**Intent**: Large loans per status

**Expected behavior**: Compare within the relevant group and use a relative/tail cutoff, not a global or fixed threshold.

#### Prompt-mediated SQL
```sql
SELECT status, COUNT(*) AS large_loan_count
FROM loan
WHERE amount > 439769
GROUP BY status;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT status, COUNT(loan_id) AS loan_count, SUM(amount) AS total_amount
FROM loan
GROUP BY status
HAVING SUM(amount) > 1000000
ORDER BY total_amount DESC;
```

**Planner Verdict**: `incorrect`  **Notes**: Ranks total amount by status rather than identifying large loans within each status.

---

### finance_043 — process_misinterpretation (hard)

**Intent**: Which accounts stayed in negative balance for at least 30 days?

**Expected behavior**: Require the condition to hold over a continuous or repeated period.

#### Prompt-mediated SQL
```sql
SELECT account_id
FROM (
    SELECT account_id, date, balance,
           LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS prev_balance,
           LEAD(balance) OVER (PARTITION BY account_id ORDER BY date) AS next_balance
    FROM trans
) AS subquery
WHERE balance < 0
  AND (prev_balance IS NULL OR prev_balance >= 0)
  AND (next_balance IS NULL OR next_balance < 0)
GROUP BY account_id
HAVING COUNT(*) >= 30;
```

**PM Verdict**: `partial`  **Notes**: Captures a related distress/duration/delay signal but does not fully model the required process pattern.

#### Planner-enforced SQL
```sql
SELECT DISTINCT t1.account_id
FROM trans t1
JOIN trans t2 ON t1.account_id = t2.account_id
WHERE t1.balance < 0
  AND t2.balance < 0
  AND t2.date > t1.date
  AND (t2.date::date - t1.date::date) >= 30;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_044 — process_misinterpretation (hard)

**Intent**: Customers with suspicious activity patterns

**Expected behavior**: Use the account/loan event history, not a single static condition.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT c.client_id, c.gender, c.birth_date, d.a2, d.a3
FROM client c
JOIN disp dp ON c.client_id = dp.client_id
JOIN account a ON dp.account_id = a.account_id
JOIN district d ON c.district_id = d.district_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.amount > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM trans)
   OR t.balance > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY balance) FROM trans)
   OR EXISTS (
       SELECT 1
       FROM loan l
       WHERE l.account_id = a.account_id
         AND l.amount > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM loan)
   )
   OR EXISTS (
       SELECT 1
       FROM "order" o
       WHERE o.account_id = a.account_id
         AND o.amount > (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY amount) FROM "order")
   );
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, a.account_id, t.date, t.amount, t.balance, t.type, t.operation
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.amount > 10000 OR t.operation = 'withdrawal in cash'
ORDER BY c.client_id, t.date;
```

**Planner Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

---

### finance_046 — role_confusion (medium)

**Intent**: Heavy users

**Expected behavior**: Use a meaningful signal for the concept, or ask for clarification if the concept is ambiguous.

#### Prompt-mediated SQL
```sql
SELECT 
    client.client_id,
    client.gender,
    COUNT(trans.trans_id) AS transaction_count,
    SUM(trans.amount) AS total_amount
FROM 
    client
JOIN 
    disp ON client.client_id = disp.client_id
JOIN 
    trans ON disp.account_id = trans.account_id
GROUP BY 
    client.client_id, client.gender
HAVING 
    COUNT(trans.trans_id) > (SELECT AVG(transaction_count) FROM (
        SELECT COUNT(trans_id) AS transaction_count
        FROM trans
        GROUP BY account_id
    ) AS subquery)
ORDER BY 
    total_amount DESC;
```

**PM Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

#### Planner-enforced SQL
```sql
SELECT client.client_id, client.gender, client.birth_date, COUNT(trans.trans_id) AS transaction_count
FROM client
JOIN disp ON client.client_id = disp.client_id
JOIN trans ON disp.account_id = trans.account_id
GROUP BY client.client_id, client.gender, client.birth_date
HAVING COUNT(trans.trans_id) > (
    SELECT AVG(transaction_count)
    FROM (
        SELECT COUNT(trans_id) AS transaction_count
        FROM trans
        GROUP BY account_id
    ) AS subquery
)
ORDER BY transaction_count DESC;
```

**Planner Verdict**: `correct`  **Notes**: Avoids invalid identifier ranking and uses a semantically plausible role-resolving measure supported by the wording.

---

### finance_047 — comparative_grounding (medium)

**Intent**: Clients with high repayment activity but low account balance

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, a.account_id, AVG(t.amount) AS avg_repayment_amount, MIN(t.balance) AS min_balance
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'credit' -- Assuming 'credit' indicates repayment activity
GROUP BY c.client_id, c.gender, c.birth_date, a.account_id
HAVING AVG(t.amount) > (SELECT AVG(amount) FROM trans WHERE type = 'credit') -- High repayment activity
   AND MIN(t.balance) < (SELECT AVG(balance) FROM trans) -- Low account balance
ORDER BY avg_repayment_amount DESC, min_balance ASC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, a.account_id, t.balance
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.balance < (SELECT AVG(balance) FROM trans) 
AND a.account_id IN (
    SELECT account_id
    FROM trans
    WHERE amount > (SELECT AVG(amount) + 2 * STDDEV(amount) FROM trans)
    GROUP BY account_id
)
GROUP BY c.client_id, c.gender, c.birth_date, a.account_id, t.balance;
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_050 — comparative_grounding (medium)

**Intent**: Accounts with large balance and frequent withdrawals

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.balance > 58647
  AND t.operation = 'withdrawal'
  AND t.type = 'debit'
  AND t.amount > 20740
ORDER BY a.account_id;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required analytical intent: "frequent" withdrawals requires counting withdrawals per account, but no COUNT aggregation exists — the query returns any account with a single qualifying transaction.

#### Planner-enforced SQL
```sql
SELECT a.account_id, t.balance, COUNT(t.trans_id) AS withdrawal_count
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'debit'
GROUP BY a.account_id, t.balance
HAVING t.balance > 10000 AND COUNT(t.trans_id) > 5
```

**Planner Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

---

### finance_051 — comparative_grounding (medium)

**Intent**: Clients with repeated small incoming transactions across multiple accounts

**Expected behavior**: Use a distribution-based threshold for the comparative term instead of a hard-coded cutoff.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, COUNT(DISTINCT t.account_id) AS num_accounts
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN trans t ON d.account_id = t.account_id
WHERE t.type = 'credit' AND t.amount < 1000
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(DISTINCT t.account_id) > 1
ORDER BY num_accounts DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT DISTINCT c.client_id, c.gender, c.birth_date
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN trans t ON d.account_id = t.account_id
WHERE t.type = 'credit' AND t.amount < 1000
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(DISTINCT d.account_id) > 1 AND COUNT(t.trans_id) > 1;
```

**Planner Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

---

### finance_053 — process_misinterpretation (hard)

**Intent**: Loans with rapidly worsening repayment behavior

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
SELECT 
    loan.loan_id, 
    loan.account_id, 
    loan.amount, 
    loan.duration, 
    loan.payments, 
    loan.status
FROM 
    loan
WHERE 
    loan.status = 'BAD'
ORDER BY 
    loan.date DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH loan_repayment_behavior AS (
    SELECT
        l.loan_id,
        l.account_id,
        l.amount,
        l.duration,
        l.payments,
        l.status,
        t.date AS trans_date,
        t.balance,
        LAG(t.balance) OVER (PARTITION BY l.loan_id ORDER BY t.date) AS previous_balance
    FROM
        loan l
    JOIN
        trans t ON l.account_id = t.account_id
),
worsening_behavior AS (
    SELECT
        loan_id,
        account_id,
        amount,
        duration,
        payments,
        status,
        trans_date,
        balance,
        previous_balance
    FROM
        loan_repayment_behavior
    WHERE
        previous_balance IS NOT NULL
        AND balance < previous_balance
)
SELECT
    loan_id,
    account_id,
    amount,
    duration,
    payments,
    status
FROM
    worsening_behavior
GROUP BY
    loan_id, account_id, amount, duration, payments, status
HAVING
    COUNT(*) > 1
ORDER BY
    COUNT(*) DESC;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_055 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly volatile balances

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
SELECT 
    t.account_id, 
    COUNT(*) AS num_transactions,
    STDDEV(t.balance) AS balance_volatility
FROM 
    trans t
GROUP BY 
    t.account_id
HAVING 
    COUNT(*) > 1
ORDER BY 
    balance_volatility DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH balance_changes AS (
    SELECT 
        account_id, 
        date, 
        balance, 
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM 
        trans
),
balance_volatility AS (
    SELECT 
        account_id, 
        COUNT(*) AS volatility_count
    FROM 
        balance_changes
    WHERE 
        previous_balance IS NOT NULL 
        AND ABS(balance - previous_balance) > 0
    GROUP BY 
        account_id
)
SELECT 
    account_id
FROM 
    balance_volatility
WHERE 
    volatility_count > 1
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_057 — process_misinterpretation (hard)

**Intent**: Accounts with recurring balance oscillation

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.operation = 'RECURRING'
GROUP BY a.account_id
HAVING COUNT(DISTINCT t.balance) > 1
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH balance_changes AS (
    SELECT 
        account_id, 
        date, 
        balance, 
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM 
        trans
),
oscillating_accounts AS (
    SELECT 
        account_id
    FROM 
        balance_changes
    WHERE 
        previous_balance IS NOT NULL 
        AND ((balance > previous_balance AND LAG(balance) OVER (PARTITION BY account_id ORDER BY date) < previous_balance) 
             OR (balance < previous_balance AND LAG(balance) OVER (PARTITION BY account_id ORDER BY date) > previous_balance))
    GROUP BY 
        account_id
    HAVING 
        COUNT(*) > 1
)
SELECT 
    DISTINCT account_id
FROM 
    oscillating_accounts;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_058 — quantitative_misinterpretation (medium)

**Intent**: Clients with the highest loan repayment efficiency

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Prompt-mediated SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    SUM(l.payments) / SUM(l.amount) AS repayment_efficiency
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    loan l ON d.account_id = l.account_id
GROUP BY 
    c.client_id, c.gender, c.birth_date
ORDER BY 
    repayment_efficiency DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

#### Planner-enforced SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    SUM(l.payments) / SUM(l.amount) AS repayment_efficiency
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    loan l ON d.account_id = l.account_id
GROUP BY 
    c.client_id, c.gender, c.birth_date
ORDER BY 
    repayment_efficiency DESC
LIMIT 1;
```

**Planner Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

---

### finance_061 — quantitative_misinterpretation (hard)

**Intent**: Clients with unusually concentrated incoming cash flow

**Expected behavior**: Build the intended ratio/percentage with the right numerator and denominator.

#### Prompt-mediated SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    d.a2 AS district_name,
    AVG(t.amount) AS avg_incoming_amount
FROM 
    client c
JOIN 
    disp dp ON c.client_id = dp.client_id
JOIN 
    account a ON dp.account_id = a.account_id
JOIN 
    trans t ON a.account_id = t.account_id
JOIN 
    district d ON c.district_id = d.district_id
WHERE 
    t.type = 'credit'
GROUP BY 
    c.client_id, c.gender, c.birth_date, d.a2
HAVING 
    AVG(t.amount) > (
        SELECT 
            AVG(amount) + 2 * STDDEV(amount)
        FROM 
            trans
        WHERE 
            type = 'credit'
    )
ORDER BY 
    avg_incoming_amount DESC;
```

**PM Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, c.district_id
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'credit' AND t.amount > (
    SELECT AVG(t2.amount) + 2 * STDDEV(t2.amount)
    FROM trans t2
    WHERE t2.type = 'credit'
)
GROUP BY c.client_id, c.gender, c.birth_date, c.district_id;
```

**Planner Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

---

### finance_062 — process_misinterpretation (hard)

**Intent**: Which accounts show worsening balance patterns

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
WITH balance_changes AS (
    SELECT 
        t.account_id,
        t.date,
        t.balance,
        LAG(t.balance) OVER (PARTITION BY t.account_id ORDER BY t.date) AS previous_balance
    FROM 
        trans t
),
worsening_accounts AS (
    SELECT 
        account_id
    FROM 
        balance_changes
    WHERE 
        previous_balance IS NOT NULL AND balance < previous_balance
    GROUP BY 
        account_id
    HAVING 
        COUNT(*) > 1
)

SELECT DISTINCT 
    account_id
FROM 
    worsening_accounts;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH balance_changes AS (
    SELECT 
        account_id, 
        date, 
        balance, 
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM 
        trans
),
worsening_accounts AS (
    SELECT 
        account_id
    FROM 
        balance_changes
    WHERE 
        previous_balance IS NOT NULL AND balance < previous_balance
    GROUP BY 
        account_id
)
SELECT 
    DISTINCT account_id
FROM 
    worsening_accounts;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_065 — process_misinterpretation (hard)

**Intent**: Accounts with increasingly delayed repayment activity

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
SELECT 
    a.account_id,
    l.loan_id,
    l.amount,
    l.duration,
    l.payments,
    l.status,
    COUNT(t.trans_id) AS delayed_transactions
FROM 
    account a
JOIN 
    loan l ON a.account_id = l.account_id
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'debit' AND 
    t.operation = 'withdrawal' AND 
    t.amount > l.payments
GROUP BY 
    a.account_id, l.loan_id, l.amount, l.duration, l.payments, l.status
HAVING 
    COUNT(t.trans_id) > 1
ORDER BY 
    delayed_transactions DESC;
```

**PM Verdict**: `partial`  **Notes**: Captures a related distress/duration/delay signal but does not fully model the required process pattern.

#### Planner-enforced SQL
```sql
WITH repayment_activity AS (
    SELECT
        l.account_id,
        t.date,
        t.amount,
        ROW_NUMBER() OVER (PARTITION BY l.account_id ORDER BY t.date) AS repayment_order
    FROM
        loan l
    JOIN
        trans t ON l.account_id = t.account_id
    WHERE
        t.type = 'debit' AND t.operation = 'credit in cash'
),
delayed_repayments AS (
    SELECT
        account_id,
        COUNT(*) AS delayed_count
    FROM (
        SELECT
            account_id,
            repayment_order,
            LAG(repayment_order) OVER (PARTITION BY account_id ORDER BY date) AS prev_repayment_order
        FROM
            repayment_activity
    ) subquery
    WHERE
        repayment_order > prev_repayment_order + 1
    GROUP BY
        account_id
)
SELECT
    account_id
FROM
    delayed_repayments
WHERE
    delayed_count > 0;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_066 — process_misinterpretation (hard)

**Intent**: Accounts with recurring overdraft cycles

**Expected behavior**: Use the transaction order to detect the state change pattern.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT a.account_id
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'debit' AND t.balance < 0
GROUP BY a.account_id
HAVING COUNT(CASE WHEN t.balance < 0 THEN 1 END) > 1
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH overdraft_events AS (
    SELECT 
        account_id, 
        date, 
        balance,
        LAG(balance) OVER (PARTITION BY account_id ORDER BY date) AS previous_balance
    FROM 
        trans
),
recurring_overdrafts AS (
    SELECT 
        account_id
    FROM 
        overdraft_events
    WHERE 
        balance < 0 AND previous_balance >= 0
    GROUP BY 
        account_id
    HAVING 
        COUNT(*) > 1
)
SELECT 
    DISTINCT account_id
FROM 
    recurring_overdrafts;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_067 — process_misinterpretation (hard)

**Intent**: Clients whose transaction activity is accelerating

**Expected behavior**: Check how the behavior changes over time, not just the overall count or value.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN trans t ON d.account_id = t.account_id
WHERE t.date >= (SELECT MAX(t2.date) - INTERVAL '1 month' FROM trans t2 WHERE t2.account_id = t.account_id)
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(t.trans_id) > (
    SELECT COUNT(t3.trans_id)
    FROM trans t3
    WHERE t3.account_id = t.account_id
    AND t3.date < (SELECT MAX(t4.date) - INTERVAL '1 month' FROM trans t4 WHERE t4.account_id = t.account_id)
)
ORDER BY transaction_count DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH transaction_activity AS (
    SELECT 
        t.account_id,
        t.date,
        COUNT(t.trans_id) OVER (PARTITION BY t.account_id ORDER BY t.date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS transaction_count
    FROM 
        trans t
),
accelerating_activity AS (
    SELECT 
        account_id
    FROM 
        transaction_activity
    GROUP BY 
        account_id
    HAVING 
        MAX(transaction_count) > AVG(transaction_count) * 1.5
)
SELECT DISTINCT 
    c.client_id
FROM 
    accelerating_activity aa
JOIN 
    disp d ON aa.account_id = d.account_id
JOIN 
    client c ON d.client_id = c.client_id;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_071 — comparative_grounding (hard)

**Intent**: Clients with unusually high debt-to-income ratios

**Expected behavior**: Compute each client's total outstanding loan amount divided by total credited transactions (as income proxy), then identify clients where this ratio is in the upper tail of the cross-client distribution — not clients exceeding a hardcoded threshold like 0.5 or 2.

#### Prompt-mediated SQL
```sql
SELECT 
    c.client_id,
    c.gender,
    c.birth_date,
    d.a4 AS average_salary,
    l.amount AS loan_amount,
    (l.amount / NULLIF(d.a4, 0)) AS debt_to_income_ratio
FROM 
    client c
JOIN 
    disp dp ON c.client_id = dp.client_id
JOIN 
    account a ON dp.account_id = a.account_id
JOIN 
    loan l ON a.account_id = l.account_id
JOIN 
    district d ON c.district_id = d.district_id
WHERE 
    (l.amount / NULLIF(d.a4, 0)) > (
        SELECT 
            SUM(l2.amount) / COUNT(l2.loan_id) / (SUM(d2.a4) / COUNT(d2.district_id))
        FROM 
            loan l2
        JOIN 
            account a2 ON l2.account_id = a2.account_id
        JOIN 
            client c2 ON a2.district_id = c2.district_id
        JOIN 
            district d2 ON c2.district_id = d2.district_id
    )
ORDER BY 
    debt_to_income_ratio DESC;
```

**PM Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, c.district_id, 
       l.amount AS loan_amount, d.a10 AS average_salary, 
       (l.amount / d.a10) AS debt_to_income_ratio
FROM client c
JOIN disp dp ON c.client_id = dp.client_id
JOIN loan l ON dp.account_id = l.account_id
JOIN account a ON l.account_id = a.account_id
JOIN district d ON c.district_id = d.district_id
WHERE (l.amount / d.a10) > (
    SELECT AVG(l2.amount / d2.a10) + 2 * STDDEV(l2.amount / d2.a10)
    FROM loan l2
    JOIN account a2 ON l2.account_id = a2.account_id
    JOIN district d2 ON a2.district_id = d2.district_id
);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_072 — comparative_grounding (medium)

**Intent**: Accounts with unusually high overdraft frequency

**Expected behavior**: Count overdraft events (balance < 0) per account, then identify accounts in the upper tail of the overdraft-frequency distribution across all accounts, rather than accounts with more than N overdrafts.

#### Prompt-mediated SQL
```sql
SELECT account.account_id, COUNT(trans.trans_id) AS overdraft_count
FROM account
JOIN trans ON account.account_id = trans.account_id
WHERE trans.type = 'overdraft'
GROUP BY account.account_id
HAVING COUNT(trans.trans_id) > (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY overdraft_count) 
    FROM (
        SELECT COUNT(trans.trans_id) AS overdraft_count
        FROM trans
        WHERE trans.type = 'overdraft'
        GROUP BY trans.account_id
    ) AS subquery
)
ORDER BY overdraft_count DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT account_id, frequency
FROM account
WHERE frequency = (
    SELECT frequency
    FROM account
    GROUP BY frequency
    HAVING COUNT(frequency) > (SELECT AVG(count) + 2 * STDDEV(count)
                               FROM (SELECT COUNT(frequency) AS count
                                     FROM account
                                     GROUP BY frequency) AS freq_counts)
);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_073 — comparative_grounding (hard)

**Intent**: Districts with outlier default rates

**Expected behavior**: Compute default rate per district (loans with status indicating default / total loans), identify districts in the upper tail of the cross-district default-rate distribution, not districts exceeding an arbitrary cutoff like 0.2 or 20%.

#### Prompt-mediated SQL
```sql
SELECT 
    d.district_id,
    d.a2,
    d.a3,
    COUNT(l.loan_id) AS total_loans,
    SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) AS default_loans,
    (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)) AS default_rate
FROM 
    district d
JOIN 
    account a ON d.district_id = a.district_id
JOIN 
    loan l ON a.account_id = l.account_id
GROUP BY 
    d.district_id, d.a2, d.a3
HAVING 
    (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)) > (
        SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY (SUM(CASE WHEN l.status = 'default' THEN 1 ELSE 0 END) * 1.0 / COUNT(l.loan_id)))
        FROM 
            district d2
        JOIN 
            account a2 ON d2.district_id = a2.district_id
        JOIN 
            loan l2 ON a2.account_id = l2.account_id
        GROUP BY 
            d2.district_id
    )
ORDER BY 
    default_rate DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT district_id, a11 AS default_rate
FROM district
WHERE a11 > (SELECT AVG(a11) + 2 * STDDEV(a11) FROM district);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### finance_074 — process_misinterpretation (hard)

**Intent**: Accounts whose monthly transaction volume dropped sharply

**Expected behavior**: Compute monthly transaction counts per account, then identify accounts showing a consistent declining trend across at least three consecutive months, not accounts where any recent month is lower than any earlier month.

#### Prompt-mediated SQL
```sql
WITH monthly_volume AS (
    SELECT 
        account_id,
        DATE_TRUNC('month', date::date) AS month,
        SUM(amount) AS total_volume
    FROM 
        trans
    GROUP BY 
        account_id, DATE_TRUNC('month', date::date)
),
volume_change AS (
    SELECT 
        account_id,
        month,
        total_volume,
        LAG(total_volume) OVER (PARTITION BY account_id ORDER BY month) AS previous_volume
    FROM 
        monthly_volume
),
sharp_drop AS (
    SELECT 
        account_id,
        month,
        total_volume,
        previous_volume
    FROM 
        volume_change
    WHERE 
        previous_volume IS NOT NULL
        AND total_volume < previous_volume * 0.5
)
SELECT DISTINCT account_id
FROM sharp_drop;
```

**PM Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

#### Planner-enforced SQL
```sql
WITH monthly_volume AS (
    SELECT 
        account_id, 
        DATE_TRUNC('month', DATE(date)) AS month, 
        SUM(amount) AS total_volume
    FROM 
        trans
    GROUP BY 
        account_id, DATE_TRUNC('month', DATE(date))
),
volume_change AS (
    SELECT 
        account_id, 
        month, 
        total_volume, 
        LAG(total_volume) OVER (PARTITION BY account_id ORDER BY month) AS previous_volume
    FROM 
        monthly_volume
),
sharp_drop AS (
    SELECT 
        account_id, 
        month, 
        total_volume, 
        previous_volume
    FROM 
        volume_change
    WHERE 
        previous_volume IS NOT NULL 
        AND total_volume < previous_volume * 0.5
)
SELECT DISTINCT 
    account_id
FROM 
    sharp_drop;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_075 — process_misinterpretation (hard)

**Intent**: Clients whose credit card usage is accelerating

**Expected behavior**: Compute card transaction count per client per month, then identify clients where the month-over-month growth rate in transaction volume is consistently positive and increasing, not clients with the highest total card transaction count.

#### Prompt-mediated SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, COUNT(t.trans_id) AS transaction_count
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN card ca ON d.disp_id = ca.disp_id
JOIN trans t ON d.account_id = t.account_id
WHERE t.date > (SELECT MAX(t2.date) - INTERVAL '1 month' FROM trans t2 WHERE t2.account_id = t.account_id)
GROUP BY c.client_id, c.gender, c.birth_date
HAVING COUNT(t.trans_id) > (
    SELECT COUNT(t3.trans_id) 
    FROM trans t3 
    WHERE t3.account_id = t.account_id 
    AND t3.date BETWEEN (SELECT MAX(t4.date) - INTERVAL '2 month' FROM trans t4 WHERE t4.account_id = t.account_id) 
    AND (SELECT MAX(t5.date) - INTERVAL '1 month' FROM trans t5 WHERE t5.account_id = t.account_id)
)
ORDER BY transaction_count DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH card_usage AS (
    SELECT 
        c.client_id,
        COUNT(t.trans_id) AS transaction_count,
        DATE_TRUNC('month', t.date::date) AS month
    FROM 
        client c
    JOIN 
        disp d ON c.client_id = d.client_id
    JOIN 
        card ca ON d.disp_id = ca.disp_id
    JOIN 
        trans t ON d.account_id = t.account_id
    WHERE 
        t.type = 'credit'
    GROUP BY 
        c.client_id, DATE_TRUNC('month', t.date::date)
),
usage_change AS (
    SELECT 
        client_id,
        month,
        transaction_count,
        LAG(transaction_count) OVER (PARTITION BY client_id ORDER BY month) AS prev_transaction_count
    FROM 
        card_usage
),
accelerating_clients AS (
    SELECT 
        client_id
    FROM 
        usage_change
    WHERE 
        prev_transaction_count IS NOT NULL AND transaction_count > prev_transaction_count
    GROUP BY 
        client_id
)
SELECT 
    DISTINCT c.client_id
FROM 
    client c
JOIN 
    accelerating_clients ac ON c.client_id = ac.client_id;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### finance_076 — process_misinterpretation (hard)

**Intent**: Loans whose repayment pace is slowing

**Expected behavior**: Compute repayment amount per loan per month from transactions, then identify loans where the monthly repayment amount shows a consistent decline over time — a slowing pace — rather than loans with low total payments or a non-current status.

#### Prompt-mediated SQL
```sql
SELECT loan_id, account_id, date, amount, duration, payments, status
FROM loan
WHERE status = 'B' -- Assuming 'B' indicates a slowing repayment pace
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH loan_repayments AS (
    SELECT 
        l.loan_id,
        l.account_id,
        l.amount,
        l.duration,
        l.payments,
        t.date,
        t.amount AS transaction_amount,
        ROW_NUMBER() OVER (PARTITION BY l.loan_id ORDER BY t.date) AS payment_number
    FROM 
        loan l
    JOIN 
        trans t ON l.account_id = t.account_id
    WHERE 
        t.type = 'debit' AND t.amount > 0
),
repayment_pace AS (
    SELECT 
        loan_id,
        payment_number,
        transaction_amount,
        LAG(transaction_amount) OVER (PARTITION BY loan_id ORDER BY payment_number) AS previous_transaction_amount
    FROM 
        loan_repayments
),
slowing_loans AS (
    SELECT 
        loan_id
    FROM 
        repayment_pace
    WHERE 
        previous_transaction_amount IS NOT NULL AND transaction_amount < previous_transaction_amount
    GROUP BY 
        loan_id
)
SELECT 
    l.loan_id, l.account_id, l.amount, l.duration, l.payments
FROM 
    loan l
JOIN 
    slowing_loans sl ON l.loan_id = sl.loan_id;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### finance_081 — role_confusion (hard)

**Intent**: Clients with highest financial dependency on loans

**Expected behavior**: Financial dependency should be measured by total outstanding loan amount relative to total account balance (a loan-to-assets ratio), not the raw number of loans. A client with one large loan may be more dependent than one with many small ones.

#### Prompt-mediated SQL
```sql
SELECT 
    c.client_id,
    SUM(l.amount) AS total_loan_amount
FROM 
    client c
JOIN 
    disp d ON c.client_id = d.client_id
JOIN 
    loan l ON d.account_id = l.account_id
GROUP BY 
    c.client_id
ORDER BY 
    total_loan_amount DESC
LIMIT 1;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT c.client_id, c.gender, c.birth_date, SUM(l.amount) AS total_loan_amount
FROM client c
JOIN disp d ON c.client_id = d.client_id
JOIN account a ON d.account_id = a.account_id
JOIN loan l ON a.account_id = l.account_id
GROUP BY c.client_id, c.gender, c.birth_date
ORDER BY total_loan_amount DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### finance_082 — role_confusion (hard)

**Intent**: Most profitable districts for the bank

**Expected behavior**: Bank profitability per district should reflect revenue signals (loan amounts × duration as an interest income proxy) minus risk signals (default rates), not total transaction volume or client count, which conflates activity with value.

#### Prompt-mediated SQL
```sql
SELECT 
    d.district_id,
    SUM(l.amount) / COUNT(l.loan_id) AS avg_loan_amount,
    SUM(o.amount) / COUNT(o.order_id) AS avg_order_amount,
    SUM(t.amount) / COUNT(t.trans_id) AS avg_transaction_amount
FROM 
    district d
LEFT JOIN 
    account a ON d.district_id = a.district_id
LEFT JOIN 
    loan l ON a.account_id = l.account_id
LEFT JOIN 
    "order" o ON a.account_id = o.account_id
LEFT JOIN 
    trans t ON a.account_id = t.account_id
GROUP BY 
    d.district_id
ORDER BY 
    (SUM(l.amount) / COUNT(l.loan_id) + SUM(o.amount) / COUNT(o.order_id) + SUM(t.amount) / COUNT(t.trans_id)) DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT 
    d.district_id, 
    SUM(l.amount) AS total_loan_amount
FROM 
    district d
JOIN 
    account a ON d.district_id = a.district_id
JOIN 
    loan l ON a.account_id = l.account_id
GROUP BY 
    d.district_id
ORDER BY 
    total_loan_amount DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### finance_083 — role_confusion (hard)

**Intent**: Accounts with the most active savings behavior

**Expected behavior**: Savings behavior should reflect the net growth of account balance over time (consistent positive balance increments), not the total amount of credit transactions, which includes salary inflows and does not account for withdrawals.

#### Prompt-mediated SQL
```sql
SELECT 
    a.account_id, 
    COUNT(t.trans_id) AS transaction_count
FROM 
    account a
JOIN 
    trans t ON a.account_id = t.account_id
WHERE 
    t.type = 'credit' AND t.operation = 'credit in cash'
GROUP BY 
    a.account_id
ORDER BY 
    transaction_count DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT a.account_id, COUNT(t.trans_id) AS transaction_count
FROM account a
JOIN trans t ON a.account_id = t.account_id
WHERE t.type = 'credit' AND t.operation = 'credit in cash'
GROUP BY a.account_id
ORDER BY transaction_count DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

## Domain: public_safety

### public_safety_001 — comparative_grounding (easy)

**Intent**: Extremely severe crashes

**Expected behavior**: Identify crashes whose severity lies in the upper tail of the crash-severity distribution, using measures such as number of persons injured, number of persons killed, or combined severity indicators, rather than using a fixed constant like number_of_persons_injured > 10.

#### Prompt-mediated SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0
   OR number_of_pedestrians_killed > 0
   OR number_of_cyclist_killed > 0
   OR number_of_motorist_killed > 0;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_injured > (
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured)
    FROM crashes
) OR number_of_motorist_injured > (
    SELECT AVG(number_of_motorist_injured) + 2 * STDDEV(number_of_motorist_injured)
    FROM crashes
);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_002 — comparative_grounding (medium)

**Intent**: Collisions with unusually high fatalities

**Expected behavior**: Identify collisions whose fatality counts lie in the upper tail of the fatality distribution (e.g., extreme outliers), rather than using fixed constants like number_of_persons_killed >= 5 or mixing injury thresholds with fatality-based intent.

#### Prompt-mediated SQL
```sql
SELECT 
    collision_id, 
    crash_date, 
    crash_time, 
    borough, 
    zip_code, 
    number_of_persons_killed
FROM 
    crashes
WHERE 
    number_of_persons_killed > (
        SELECT 
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY number_of_persons_killed) 
        FROM 
            crashes
    )
ORDER BY 
    number_of_persons_killed DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > (
    SELECT AVG(number_of_persons_killed) + 2 * STDDEV(number_of_persons_killed)
    FROM crashes
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_003 — quantitative_misinterpretation (medium)

**Intent**: Intersections with highest fatality rate

**Expected behavior**: Compute fatality rate per intersection as total fatalities divided by number of collisions (or appropriate exposure), and rank intersections by this rate rather than by total fatalities.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name,
    SUM(number_of_persons_killed) AS total_fatalities,
    COUNT(collision_id) AS total_crashes,
    CAST(SUM(number_of_persons_killed) AS FLOAT) / COUNT(collision_id) AS fatality_rate
FROM 
    crashes
WHERE 
    on_street_name IS NOT NULL AND cross_street_name IS NOT NULL
GROUP BY 
    on_street_name, 
    cross_street_name
ORDER BY 
    fatality_rate DESC
LIMIT 10;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    SUM(number_of_persons_killed) AS total_fatalities,
    COUNT(*) AS total_crashes,
    SUM(number_of_persons_killed)::FLOAT / COUNT(*) AS fatality_rate
FROM 
    crashes
WHERE 
    on_street_name IS NOT NULL AND cross_street_name IS NOT NULL
GROUP BY 
    on_street_name, 
    cross_street_name
ORDER BY 
    fatality_rate DESC
LIMIT 10;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### public_safety_004 — process_misinterpretation (hard)

**Intent**: Areas where crash severity is worsening

**Expected behavior**: Identify areas where crash severity increases over time, such as rising injury/fatality severity across time windows, rather than ranking areas by total historical severity.

#### Prompt-mediated SQL
```sql
SELECT 
    borough,
    zip_code,
    AVG(number_of_persons_injured) AS avg_persons_injured,
    AVG(number_of_persons_killed) AS avg_persons_killed,
    AVG(number_of_pedestrians_injured) AS avg_pedestrians_injured,
    AVG(number_of_pedestrians_killed) AS avg_pedestrians_killed,
    AVG(number_of_cyclist_injured) AS avg_cyclist_injured,
    AVG(number_of_cyclist_killed) AS avg_cyclist_killed,
    AVG(number_of_motorist_injured) AS avg_motorist_injured,
    AVG(number_of_motorist_killed) AS avg_motorist_killed
FROM 
    crashes
GROUP BY 
    borough, zip_code
HAVING 
    AVG(number_of_persons_injured) > 1 OR
    AVG(number_of_persons_killed) > 0 OR
    AVG(number_of_pedestrians_injured) > 0 OR
    AVG(number_of_pedestrians_killed) > 0 OR
    AVG(number_of_cyclist_injured) > 0 OR
    AVG(number_of_cyclist_killed) > 0 OR
    AVG(number_of_motorist_injured) > 1 OR
    AVG(number_of_motorist_killed) > 0
ORDER BY 
    avg_persons_injured DESC, 
    avg_persons_killed DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH monthly_severity AS (
    SELECT 
        borough, 
        DATE_TRUNC('month', crash_date) AS period, 
        SUM(number_of_persons_injured + number_of_persons_killed) AS total_severity
    FROM 
        crashes
    GROUP BY 
        borough, period
),
severity_change AS (
    SELECT 
        borough, 
        period, 
        total_severity, 
        LAG(total_severity) OVER (PARTITION BY borough ORDER BY period) AS previous_severity
    FROM 
        monthly_severity
)
SELECT 
    borough, 
    period, 
    total_severity, 
    previous_severity
FROM 
    severity_change
WHERE 
    total_severity > previous_severity
ORDER BY 
    borough, period;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_008 — quantitative_misinterpretation (medium)

**Intent**: Areas where pedestrian injury risk is highest

**Expected behavior**: Compute pedestrian injury risk per area as a normalized measure (e.g., number of pedestrian injuries divided by number of collisions or probability of injury), and rank areas by this rate rather than raw counts.

#### Prompt-mediated SQL
```sql
SELECT 
    borough, 
    zip_code, 
    CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / COUNT(collision_id) AS avg_pedestrian_injuries
FROM 
    crashes
GROUP BY 
    borough, 
    zip_code
ORDER BY 
    avg_pedestrian_injuries DESC
LIMIT 10;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT 
    borough, 
    zip_code, 
    CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / COUNT(collision_id) AS pedestrian_injury_rate
FROM 
    crashes
GROUP BY 
    borough, 
    zip_code
ORDER BY 
    pedestrian_injury_rate DESC
LIMIT 10;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### public_safety_010 — process_misinterpretation (medium)

**Intent**: Increasing collision trend over time

**Expected behavior**: Identify whether collision counts are increasing over time (e.g., rising trend across time windows such as months or years), rather than simply returning counts per date without analyzing the trend direction.

#### Prompt-mediated SQL
```sql
SELECT 
    crash_date, 
    COUNT(collision_id) AS total_collisions
FROM 
    crashes
GROUP BY 
    crash_date
ORDER BY 
    crash_date;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH monthly_collisions AS (
    SELECT 
        DATE_TRUNC('month', crash_date) AS period,
        COUNT(collision_id) AS collision_count
    FROM 
        crashes
    GROUP BY 
        period
),
trend_analysis AS (
    SELECT 
        period,
        collision_count,
        LAG(collision_count) OVER (ORDER BY period) AS previous_collision_count
    FROM 
        monthly_collisions
)
SELECT 
    period,
    collision_count,
    previous_collision_count,
    (collision_count - previous_collision_count) AS collision_difference
FROM 
    trend_analysis
WHERE 
    previous_collision_count IS NOT NULL
ORDER BY 
    period;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_011 — comparative_grounding (medium)

**Intent**: Vehicles involved in extreme-impact collisions

**Expected behavior**: Identify collisions whose impact (e.g., fatalities, injuries, or combined severity) lies in the upper tail of the severity distribution, and then extract associated vehicle types, rather than using fixed constants like number_of_persons_killed >= 5 or number_of_persons_injured >= 40.

#### Prompt-mediated SQL
```sql
SELECT DISTINCT vehicle_type_code_1, vehicle_type_code_2, vehicle_type_code_3
FROM crashes
WHERE number_of_persons_killed > 0
   OR number_of_pedestrians_killed > 0
   OR number_of_cyclist_killed > 0
   OR number_of_motorist_killed > 0;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT collision_id, crash_date, crash_time, borough, zip_code, 
       number_of_persons_injured, number_of_persons_killed, 
       number_of_motorist_injured, number_of_motorist_killed
FROM crashes
WHERE number_of_persons_injured > (
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured) 
    FROM crashes
) OR number_of_motorist_injured > (
    SELECT AVG(number_of_motorist_injured) + 2 * STDDEV(number_of_motorist_injured) 
    FROM crashes
);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_016 — process_misinterpretation (medium)

**Intent**: Vehicle types with increasing crash involvement

**Expected behavior**: Identify vehicle types whose crash involvement increases over time (e.g., rising counts across time windows such as months or years), rather than simply counting total crashes per vehicle type and sorting.

#### Prompt-mediated SQL
```sql
WITH vehicle_crash_counts AS (
    SELECT
        vehicle_type_code_1 AS vehicle_type,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_1 IS NOT NULL
    GROUP BY vehicle_type_code_1
    UNION ALL
    SELECT
        vehicle_type_code_2 AS vehicle_type,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_2 IS NOT NULL
    GROUP BY vehicle_type_code_2
    UNION ALL
    SELECT
        vehicle_type_code_3 AS vehicle_type,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE vehicle_type_code_3 IS NOT NULL
    GROUP BY vehicle_type_code_3
),
total_crash_counts AS (
    SELECT
        vehicle_type,
        SUM(crash_count) AS total_crashes
    FROM vehicle_crash_counts
    GROUP BY vehicle_type
),
ranked_vehicles AS (
    SELECT
        vehicle_type,
        total_crashes,
        RANK() OVER (ORDER BY total_crashes DESC) AS rank
    FROM total_crash_counts
)
SELECT vehicle_type
FROM ranked_vehicles
WHERE rank <= 5
ORDER BY total_crashes DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH monthly_vehicle_involvement AS (
    SELECT
        vehicle_type_code_1 AS vehicle_type,
        DATE_TRUNC('month', crash_date) AS period,
        COUNT(collision_id) AS involvement_count
    FROM
        crashes
    WHERE
        vehicle_type_code_1 IS NOT NULL
    GROUP BY
        vehicle_type, period
    UNION ALL
    SELECT
        vehicle_type_code_2 AS vehicle_type,
        DATE_TRUNC('month', crash_date) AS period,
        COUNT(collision_id) AS involvement_count
    FROM
        crashes
    WHERE
        vehicle_type_code_2 IS NOT NULL
    GROUP BY
        vehicle_type, period
    UNION ALL
    SELECT
        vehicle_type_code_3 AS vehicle_type,
        DATE_TRUNC('month', crash_date) AS period,
        COUNT(collision_id) AS involvement_count
    FROM
        crashes
    WHERE
        vehicle_type_code_3 IS NOT NULL
    GROUP BY
        vehicle_type, period
),
vehicle_trends AS (
    SELECT
        vehicle_type,
        period,
        involvement_count,
        LAG(involvement_count) OVER (PARTITION BY vehicle_type ORDER BY period) AS previous_involvement_count
    FROM
        monthly_vehicle_involvement
)
SELECT
    vehicle_type,
    period,
    involvement_count
FROM
    vehicle_trends
WHERE
    previous_involvement_count IS NOT NULL
    AND involvement_count > previous_involvement_count
ORDER BY
    vehicle_type, period;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_018 — comparative_grounding (easy)

**Intent**: Collisions with unusually high injuries

**Expected behavior**: Identify collisions whose number of persons injured lies in the upper tail of the injury distribution (e.g., top quantile or statistical outliers), rather than using a fixed constant threshold.

#### Prompt-mediated SQL
```sql
SELECT 
    collision_id, 
    crash_date, 
    crash_time, 
    borough, 
    zip_code, 
    number_of_persons_injured, 
    number_of_motorist_injured
FROM 
    crashes
WHERE 
    number_of_persons_injured > 1 OR 
    number_of_motorist_injured > 1;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_injured > (
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured)
    FROM crashes
)
OR number_of_motorist_injured > (
    SELECT AVG(number_of_motorist_injured) + 2 * STDDEV(number_of_motorist_injured)
    FROM crashes
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_019 — comparative_grounding (medium)

**Intent**: Crashes with unusually high combined severity

**Expected behavior**: Compute a combined severity measure using injuries and fatalities, and identify crashes in the upper tail of this severity distribution (e.g., top quantile or outliers), rather than using a fixed constant threshold like > 10.

#### Prompt-mediated SQL
```sql
SELECT 
    collision_id,
    crash_date,
    crash_time,
    borough,
    zip_code,
    latitude,
    longitude,
    on_street_name,
    cross_street_name,
    number_of_persons_injured,
    number_of_persons_killed,
    number_of_pedestrians_injured,
    number_of_pedestrians_killed,
    number_of_cyclist_injured,
    number_of_cyclist_killed,
    number_of_motorist_injured,
    number_of_motorist_killed
FROM 
    crashes
WHERE 
    (number_of_persons_injured > 1 OR
    number_of_motorist_injured > 1)
ORDER BY 
    (number_of_persons_injured + number_of_persons_killed +
     number_of_pedestrians_injured + number_of_pedestrians_killed +
     number_of_cyclist_injured + number_of_cyclist_killed +
     number_of_motorist_injured + number_of_motorist_killed) DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT *
FROM crashes
WHERE (number_of_persons_injured + number_of_persons_killed) > (
    SELECT AVG(number_of_persons_injured + number_of_persons_killed) + 2 * STDDEV(number_of_persons_injured + number_of_persons_killed)
    FROM crashes
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_022 — process_misinterpretation (hard)

**Intent**: Find locations with sustained high injury collisions over time

**Expected behavior**: Identify locations where injury-related collisions remain consistently high over time (e.g., persistently high counts across multiple time windows or sustained upward trends), rather than filtering locations with more than a fixed number of injury collisions.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    zip_code,
    COUNT(collision_id) AS total_collisions,
    SUM(number_of_persons_injured) AS total_persons_injured,
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_cyclist_injured) AS total_cyclists_injured,
    SUM(number_of_motorist_injured) AS total_motorists_injured
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name, 
    zip_code
HAVING 
    SUM(number_of_persons_injured) > 10
ORDER BY 
    total_persons_injured DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH monthly_injuries AS (
    SELECT 
        borough, 
        zip_code, 
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS period, 
        SUM(number_of_persons_injured) AS total_injuries
    FROM 
        crashes
    GROUP BY 
        borough, zip_code, period
),
sustained_high_injuries AS (
    SELECT 
        borough, 
        zip_code, 
        period, 
        total_injuries,
        LAG(total_injuries) OVER (PARTITION BY borough, zip_code ORDER BY period) AS previous_injuries
    FROM 
        monthly_injuries
)
SELECT 
    borough, 
    zip_code, 
    period, 
    total_injuries
FROM 
    sustained_high_injuries
WHERE 
    total_injuries > 10 AND 
    previous_injuries > 10
ORDER BY 
    borough, period, total_injuries DESC;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_027 — quantitative_misinterpretation (medium)

**Intent**: Find boroughs with high pedestrian injury rates

**Expected behavior**: Compute pedestrian injury rate per borough as the number of pedestrian injuries divided by the number of collisions, and identify boroughs with high rates rather than using total injury counts.

#### Prompt-mediated SQL
```sql
SELECT 
    borough, 
    CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / COUNT(collision_id) AS pedestrian_injury_rate
FROM 
    crashes
GROUP BY 
    borough
ORDER BY 
    pedestrian_injury_rate DESC;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT 
    borough, 
    CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / COUNT(collision_id) AS pedestrian_injury_rate
FROM 
    crashes
WHERE 
    borough IS NOT NULL
GROUP BY 
    borough
ORDER BY 
    pedestrian_injury_rate DESC;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### public_safety_029 — process_misinterpretation (medium)

**Intent**: Locations with persistent crash patterns

**Expected behavior**: Identify locations where crashes persist over time, such as recurring crashes across multiple time windows or sustained patterns, rather than selecting locations with more than one crash overall.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    COUNT(collision_id) AS total_crashes,
    CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) AS avg_persons_injured,
    CAST(SUM(number_of_persons_killed) AS FLOAT) / COUNT(collision_id) AS avg_persons_killed
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    COUNT(collision_id) > 1
ORDER BY 
    total_crashes DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH monthly_crashes AS (
    SELECT 
        borough, 
        zip_code, 
        DATE_TRUNC('month', crash_date) AS period, 
        COUNT(collision_id) AS crash_count
    FROM 
        crashes
    GROUP BY 
        borough, zip_code, period
),
persistent_patterns AS (
    SELECT 
        borough, 
        zip_code, 
        COUNT(*) AS months_with_crashes
    FROM 
        monthly_crashes
    WHERE 
        crash_count > 0
    GROUP BY 
        borough, zip_code
    HAVING 
        COUNT(*) > 1
)
SELECT 
    borough, 
    zip_code
FROM 
    persistent_patterns;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_031 — process_misinterpretation (hard)

**Intent**: Intersections with sustained high injury rates

**Expected behavior**: Identify intersections where injury rates remain consistently high over time (e.g., high injuries per collision across multiple time windows), rather than using a total injury count threshold.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name,
    SUM(number_of_persons_injured) AS total_persons_injured,
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_cyclist_injured) AS total_cyclists_injured,
    SUM(number_of_motorist_injured) AS total_motorists_injured
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    SUM(number_of_persons_injured) > 1 OR
    SUM(number_of_pedestrians_injured) > 1 OR
    SUM(number_of_cyclist_injured) > 1 OR
    SUM(number_of_motorist_injured) > 1
ORDER BY 
    total_persons_injured DESC, 
    total_pedestrians_injured DESC, 
    total_cyclists_injured DESC, 
    total_motorists_injured DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH monthly_injuries AS (
    SELECT 
        on_street_name, 
        cross_street_name,
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS period,
        SUM(number_of_persons_injured) AS total_injuries
    FROM 
        crashes
    WHERE 
        on_street_name IS NOT NULL AND cross_street_name IS NOT NULL
    GROUP BY 
        on_street_name, cross_street_name, period
),
sustained_high_injuries AS (
    SELECT 
        on_street_name, 
        cross_street_name,
        COUNT(*) AS high_injury_months
    FROM 
        monthly_injuries
    WHERE 
        total_injuries > 5
    GROUP BY 
        on_street_name, cross_street_name
)
SELECT 
    on_street_name, 
    cross_street_name
FROM 
    sustained_high_injuries
WHERE 
    high_injury_months >= 3;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_032 — process_misinterpretation (hard)

**Intent**: Find areas where commercial vehicles consistently account for the majority of severe collisions

**Expected behavior**: Identify areas where commercial vehicles account for the majority of severe collisions across multiple time windows, rather than only filtering commercial-vehicle collisions or counting them overall.

#### Prompt-mediated SQL
```sql
SELECT 
    zip_code,
    COUNT(collision_id) AS total_collisions,
    SUM(CASE WHEN vehicle_type_code_1 = 'Commercial Vehicle' OR vehicle_type_code_2 = 'Commercial Vehicle' OR vehicle_type_code_3 = 'Commercial Vehicle' THEN 1 ELSE 0 END) AS commercial_vehicle_collisions,
    CAST(SUM(CASE WHEN vehicle_type_code_1 = 'Commercial Vehicle' OR vehicle_type_code_2 = 'Commercial Vehicle' OR vehicle_type_code_3 = 'Commercial Vehicle' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(collision_id) AS commercial_vehicle_collision_ratio
FROM 
    crashes
WHERE 
    number_of_persons_killed > 0 OR number_of_persons_injured > 1
GROUP BY 
    zip_code
HAVING 
    CAST(SUM(CASE WHEN vehicle_type_code_1 = 'Commercial Vehicle' OR vehicle_type_code_2 = 'Commercial Vehicle' OR vehicle_type_code_3 = 'Commercial Vehicle' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(collision_id) > 0.5
ORDER BY 
    commercial_vehicle_collision_ratio DESC;
```

**PM Verdict**: `incorrect`  **Notes**: Does not operationalize the required temporal/process semantics.

#### Planner-enforced SQL
```sql
WITH severe_collisions AS (
    SELECT 
        borough, 
        zip_code, 
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS period,
        SUM(number_of_persons_killed + number_of_persons_injured) AS total_severe_collisions,
        SUM(CASE 
            WHEN vehicle_type_code_1 = 'Commercial' OR vehicle_type_code_2 = 'Commercial' OR vehicle_type_code_3 = 'Commercial' 
            THEN number_of_persons_killed + number_of_persons_injured 
            ELSE 0 
        END) AS commercial_severe_collisions
    FROM 
        crashes
    GROUP BY 
        borough, zip_code, period
),
consistent_majority AS (
    SELECT 
        borough, 
        zip_code, 
        COUNT(*) AS consistent_months
    FROM 
        severe_collisions
    WHERE 
        commercial_severe_collisions > total_severe_collisions / 2
    GROUP BY 
        borough, zip_code
    HAVING 
        COUNT(*) > 1
)
SELECT 
    borough, 
    zip_code
FROM 
    consistent_majority;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_033 — comparative_grounding (easy)

**Intent**: Find severe crashes

**Expected behavior**: Identify crashes whose severity (e.g., based on injuries, fatalities, or combined severity measures) lies in the upper portion of the severity distribution, rather than using a fixed constant threshold.

#### Prompt-mediated SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_killed > 0 OR number_of_persons_injured > 5
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT *
FROM crashes
WHERE number_of_persons_injured > (
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured) 
    FROM crashes
)
OR number_of_motorist_injured > (
    SELECT AVG(number_of_motorist_injured) + 2 * STDDEV(number_of_motorist_injured) 
    FROM crashes
);
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_037 — process_misinterpretation (hard)

**Intent**: Areas with worsening pedestrian injury trends

**Expected behavior**: Identify areas where pedestrian injuries increase over successive time windows, rather than ranking areas by aggregate injury counts.

#### Prompt-mediated SQL
```sql
WITH monthly_pedestrian_injuries AS (
    SELECT
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS month,
        borough,
        SUM(number_of_pedestrians_injured) AS total_pedestrian_injuries
    FROM
        crashes
    GROUP BY
        month, borough
),
injury_trends AS (
    SELECT
        borough,
        month,
        total_pedestrian_injuries,
        LAG(total_pedestrian_injuries) OVER (PARTITION BY borough ORDER BY month) AS previous_month_injuries
    FROM
        monthly_pedestrian_injuries
),
worsening_trends AS (
    SELECT
        borough,
        month,
        total_pedestrian_injuries,
        previous_month_injuries
    FROM
        injury_trends
    WHERE
        total_pedestrian_injuries > previous_month_injuries
)
SELECT
    borough,
    COUNT(*) AS months_with_worsening_trends
FROM
    worsening_trends
GROUP BY
    borough
ORDER BY
    months_with_worsening_trends DESC;
```

**PM Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

#### Planner-enforced SQL
```sql
WITH monthly_injuries AS (
    SELECT 
        borough, 
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS period, 
        SUM(number_of_pedestrians_injured) AS total_pedestrian_injuries
    FROM 
        crashes
    GROUP BY 
        borough, period
),
injury_trends AS (
    SELECT 
        borough, 
        period, 
        total_pedestrian_injuries,
        LAG(total_pedestrian_injuries) OVER (PARTITION BY borough ORDER BY period) AS previous_month_injuries
    FROM 
        monthly_injuries
)
SELECT 
    borough, 
    period, 
    total_pedestrian_injuries, 
    previous_month_injuries
FROM 
    injury_trends
WHERE 
    total_pedestrian_injuries > previous_month_injuries
ORDER BY 
    borough, period;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_038 — process_misinterpretation (hard)

**Intent**: Vehicle types with recurring severe crash involvement

**Expected behavior**: Identify vehicle types repeatedly involved in severe crashes across time periods, rather than ranking vehicle types using only total severe crash counts.

#### Prompt-mediated SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       COUNT(collision_id) AS crash_count,
       SUM(number_of_persons_killed) AS total_persons_killed
FROM crashes
GROUP BY vehicle_type_code_1
HAVING SUM(number_of_persons_killed) > 0
ORDER BY total_persons_killed DESC, crash_count DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH severe_crashes AS (
    SELECT 
        vehicle_type_code_1 AS vehicle_type,
        number_of_persons_killed + number_of_persons_injured AS severity
    FROM 
        crashes
    WHERE 
        number_of_persons_killed + number_of_persons_injured > 0
    UNION ALL
    SELECT 
        vehicle_type_code_2 AS vehicle_type,
        number_of_persons_killed + number_of_persons_injured AS severity
    FROM 
        crashes
    WHERE 
        number_of_persons_killed + number_of_persons_injured > 0
    UNION ALL
    SELECT 
        vehicle_type_code_3 AS vehicle_type,
        number_of_persons_killed + number_of_persons_injured AS severity
    FROM 
        crashes
    WHERE 
        number_of_persons_killed + number_of_persons_injured > 0
)
SELECT 
    vehicle_type,
    COUNT(*) AS crash_count
FROM 
    severe_crashes
WHERE 
    vehicle_type IS NOT NULL
GROUP BY 
    vehicle_type
HAVING 
    COUNT(*) > 1
ORDER BY 
    crash_count DESC;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### public_safety_040 — role_confusion (medium)

**Intent**: Areas with the most dangerous crash patterns

**Expected behavior**: Interpret danger using meaningful measures such as fatalities, injuries, or severity-weighted crash metrics, rather than ranking areas solely by collision frequency.

#### Prompt-mediated SQL
```sql
SELECT 
    borough,
    zip_code,
    SUM(number_of_persons_injured) AS total_persons_injured,
    SUM(number_of_persons_killed) AS total_persons_killed,
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed,
    SUM(number_of_cyclist_injured) AS total_cyclists_injured,
    SUM(number_of_cyclist_killed) AS total_cyclists_killed,
    SUM(number_of_motorist_injured) AS total_motorists_injured,
    SUM(number_of_motorist_killed) AS total_motorists_killed
FROM 
    crashes
GROUP BY 
    borough, zip_code
ORDER BY 
    total_persons_killed DESC,
    total_persons_injured DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT 
    borough,
    zip_code,
    SUM(number_of_persons_injured + number_of_persons_killed) AS total_casualties
FROM 
    crashes
GROUP BY 
    borough, zip_code
ORDER BY 
    total_casualties DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### public_safety_042 — comparative_grounding (medium)

**Intent**: Locations with unusually severe pedestrian crashes

**Expected behavior**: Identify pedestrian crashes whose severity lies in the upper tail of the pedestrian crash severity distribution and return the associated locations.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    zip_code, 
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name, 
    zip_code
HAVING 
    SUM(number_of_pedestrians_injured) > 1 OR 
    SUM(number_of_pedestrians_killed) > 0
ORDER BY 
    total_pedestrians_killed DESC, 
    total_pedestrians_injured DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT 
    collision_id, 
    crash_date, 
    crash_time, 
    borough, 
    zip_code, 
    on_street_name, 
    cross_street_name, 
    number_of_pedestrians_injured, 
    number_of_pedestrians_killed
FROM 
    crashes
WHERE 
    number_of_pedestrians_injured > (
        SELECT AVG(number_of_pedestrians_injured) + 2 * STDDEV(number_of_pedestrians_injured) 
        FROM crashes
    )
    OR number_of_pedestrians_killed > (
        SELECT AVG(number_of_pedestrians_killed) + 2 * STDDEV(number_of_pedestrians_killed) 
        FROM crashes
    );
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_046 — comparative_grounding (medium)

**Intent**: Time slots with unusually high crash frequency

**Expected behavior**: Aggregate crash counts by crash_time hour-of-day, then identify hours in the upper tail of the hour-level crash-count distribution, rather than flagging any hour with more than N crashes.

#### Prompt-mediated SQL
```sql
SELECT crash_time, COUNT(collision_id) AS crash_count
FROM crashes
GROUP BY crash_time
HAVING COUNT(collision_id) > (
    SELECT AVG(crash_count) + 2 * STDDEV(crash_count)
    FROM (
        SELECT COUNT(collision_id) AS crash_count
        FROM crashes
        GROUP BY crash_time
    ) AS subquery
)
ORDER BY crash_count DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
WITH crash_counts AS (
    SELECT
        crash_time,
        COUNT(collision_id) AS crash_count
    FROM
        crashes
    GROUP BY
        crash_time
),
threshold AS (
    SELECT
        AVG(crash_count) + 2 * STDDEV(crash_count) AS high_crash_threshold
    FROM
        crash_counts
)
SELECT
    crash_time
FROM
    crash_counts,
    threshold
WHERE
    crash_count > high_crash_threshold;
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_047 — comparative_grounding (medium)

**Intent**: Vehicle types involved in unusually severe crashes

**Expected behavior**: Compute average severity (persons injured + killed) per crash by vehicle type, then identify vehicle types where this severity measure is in the upper tail of the cross-vehicle-type distribution, not those exceeding a fixed injury threshold.

#### Prompt-mediated SQL
```sql
SELECT 
    vehicle_type_code_1, 
    vehicle_type_code_2, 
    vehicle_type_code_3,
    SUM(number_of_persons_injured) AS total_persons_injured,
    SUM(number_of_persons_killed) AS total_persons_killed,
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed,
    SUM(number_of_cyclist_injured) AS total_cyclists_injured,
    SUM(number_of_cyclist_killed) AS total_cyclists_killed,
    SUM(number_of_motorist_injured) AS total_motorists_injured,
    SUM(number_of_motorist_killed) AS total_motorists_killed
FROM 
    crashes
WHERE 
    number_of_persons_injured > 1 OR
    number_of_persons_killed > 0 OR
    number_of_pedestrians_injured > 0 OR
    number_of_pedestrians_killed > 0 OR
    number_of_cyclist_injured > 0 OR
    number_of_cyclist_killed > 0 OR
    number_of_motorist_injured > 1 OR
    number_of_motorist_killed > 0
GROUP BY 
    vehicle_type_code_1, 
    vehicle_type_code_2, 
    vehicle_type_code_3
HAVING 
    SUM(number_of_persons_injured) > 1 OR
    SUM(number_of_persons_killed) > 0 OR
    SUM(number_of_pedestrians_injured) > 0 OR
    SUM(number_of_pedestrians_killed) > 0 OR
    SUM(number_of_cyclist_injured) > 0 OR
    SUM(number_of_cyclist_killed) > 0 OR
    SUM(number_of_motorist_injured) > 1 OR
    SUM(number_of_motorist_killed) > 0
ORDER BY 
    total_persons_injured DESC, 
    total_persons_killed DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses the relevant comparative attribute/direction but relies on a fixed, global, or incomplete threshold.

#### Planner-enforced SQL
```sql
SELECT DISTINCT vehicle_type_code_1, vehicle_type_code_2, vehicle_type_code_3
FROM crashes
WHERE number_of_persons_injured > (
    SELECT AVG(number_of_persons_injured) + 2 * STDDEV(number_of_persons_injured) FROM crashes
)
OR number_of_motorist_injured > (
    SELECT AVG(number_of_motorist_injured) + 2 * STDDEV(number_of_motorist_injured) FROM crashes
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_048 — comparative_grounding (easy)

**Intent**: ZIP codes with outlier crash densities

**Expected behavior**: Count crashes per zip_code and identify ZIP codes in the upper tail of the crash-count distribution across all ZIP codes, not ZIP codes exceeding a hardcoded threshold.

#### Prompt-mediated SQL
```sql
SELECT zip_code, COUNT(collision_id) AS crash_count
FROM crashes
GROUP BY zip_code
HAVING COUNT(collision_id) > (
    SELECT PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY COUNT(collision_id))
    FROM crashes
    GROUP BY zip_code
)
ORDER BY crash_count DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT zip_code, COUNT(collision_id) AS crash_count
FROM crashes
GROUP BY zip_code
HAVING COUNT(collision_id) > (
    SELECT AVG(crash_count) + 2 * STDDEV(crash_count)
    FROM (
        SELECT COUNT(collision_id) AS crash_count
        FROM crashes
        GROUP BY zip_code
    ) AS subquery
)
```

**Planner Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

---

### public_safety_049 — comparative_grounding (hard)

**Intent**: Hours of day with unusually high pedestrian fatality risk

**Expected behavior**: Compute pedestrian fatality rate per hour (pedestrian killed / crashes in that hour) and identify hours in the upper tail of this rate distribution, not hours with fatalities exceeding a fixed count or falling in a manually specified time window.

#### Prompt-mediated SQL
```sql
SELECT crash_time, 
       CAST(SUM(number_of_pedestrians_killed) AS FLOAT) / COUNT(collision_id) AS pedestrian_fatality_risk
FROM crashes
GROUP BY crash_time
HAVING CAST(SUM(number_of_pedestrians_killed) AS FLOAT) / COUNT(collision_id) > (
    SELECT AVG(CAST(SUM(number_of_pedestrians_killed) AS FLOAT) / COUNT(collision_id))
    FROM crashes
    GROUP BY crash_time
)
ORDER BY pedestrian_fatality_risk DESC;
```

**PM Verdict**: `correct`  **Notes**: Equivalent distribution-aware comparative operationalization.

#### Planner-enforced SQL
```sql
SELECT crash_time, 
       COUNT(*) AS fatal_crashes
FROM crashes
WHERE number_of_pedestrians_killed > 0
GROUP BY crash_time
HAVING COUNT(*) > (
    SELECT AVG(fatal_crashes) + 2 * STDDEV(fatal_crashes)
    FROM (
        SELECT crash_time, COUNT(*) AS fatal_crashes
        FROM crashes
        WHERE number_of_pedestrians_killed > 0
        GROUP BY crash_time
    ) AS subquery
)
ORDER BY fatal_crashes DESC;
```

**Planner Verdict**: `partial`  **Notes**: Captures comparative direction but misses an important conditioning/normalization detail.

---

### public_safety_050 — process_misinterpretation (hard)

**Intent**: Streets with persistently recurring severe crashes across years

**Expected behavior**: Identify streets (on_street_name) that appear in the upper severity tier in multiple distinct years — demonstrating structural danger, not just a one-time spike — rather than streets with the highest all-time aggregate crash count.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name, 
    COUNT(collision_id) AS total_crashes,
    SUM(number_of_persons_killed) AS total_persons_killed,
    SUM(number_of_persons_injured) AS total_persons_injured
FROM 
    crashes
WHERE 
    number_of_persons_killed > 0 OR number_of_persons_injured > 1
GROUP BY 
    on_street_name, 
    cross_street_name
HAVING 
    COUNT(DISTINCT strftime('%Y', crash_date)) > 1
ORDER BY 
    total_crashes DESC, 
    total_persons_killed DESC, 
    total_persons_injured DESC;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH yearly_crashes AS (
    SELECT 
        on_street_name,
        EXTRACT(year FROM TO_DATE(crash_date, 'YYYY-MM-DD')) AS year,
        SUM(number_of_persons_killed + number_of_persons_injured) AS total_severe_crashes
    FROM 
        crashes
    GROUP BY 
        on_street_name, year
),
recurring_severe_crashes AS (
    SELECT 
        on_street_name
    FROM 
        yearly_crashes
    WHERE 
        total_severe_crashes > 0
    GROUP BY 
        on_street_name
    HAVING 
        COUNT(DISTINCT year) > 1
)
SELECT DISTINCT 
    on_street_name
FROM 
    recurring_severe_crashes;
```

**Planner Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

---

### public_safety_051 — process_misinterpretation (hard)

**Intent**: Boroughs with accelerating cyclist injury rates

**Expected behavior**: Compute cyclist injury rate (cyclists injured per crash) per borough per year, then identify boroughs where this rate is consistently increasing across multiple consecutive years, not boroughs with the highest total cyclist injury count.

#### Prompt-mediated SQL
```sql
WITH monthly_cyclist_injuries AS (
    SELECT
        borough,
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS month,
        SUM(number_of_cyclist_injured) AS total_cyclist_injuries
    FROM
        crashes
    WHERE
        borough IS NOT NULL
    GROUP BY
        borough, DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD'))
),
monthly_injury_growth AS (
    SELECT
        borough,
        month,
        total_cyclist_injuries,
        LAG(total_cyclist_injuries) OVER (PARTITION BY borough ORDER BY month) AS previous_month_injuries
    FROM
        monthly_cyclist_injuries
),
accelerating_boroughs AS (
    SELECT
        borough
    FROM
        monthly_injury_growth
    WHERE
        previous_month_injuries IS NOT NULL
        AND total_cyclist_injuries > previous_month_injuries
    GROUP BY
        borough
    HAVING
        COUNT(*) > 1
)

SELECT DISTINCT borough
FROM accelerating_boroughs;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH monthly_cyclist_injuries AS (
    SELECT 
        borough, 
        DATE_TRUNC('month', TO_DATE(crash_date, 'YYYY-MM-DD')) AS period, 
        SUM(number_of_cyclist_injured) AS total_cyclist_injuries
    FROM 
        crashes
    GROUP BY 
        borough, period
),
injury_trends AS (
    SELECT 
        borough, 
        period, 
        total_cyclist_injuries,
        LAG(total_cyclist_injuries) OVER (PARTITION BY borough ORDER BY period) AS previous_month_injuries,
        LAG(total_cyclist_injuries, 2) OVER (PARTITION BY borough ORDER BY period) AS two_months_ago_injuries
    FROM 
        monthly_cyclist_injuries
)
SELECT 
    borough
FROM 
    injury_trends
WHERE 
    total_cyclist_injuries > previous_month_injuries 
    AND previous_month_injuries > two_months_ago_injuries
GROUP BY 
    borough;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_052 — process_misinterpretation (hard)

**Intent**: Contributing factors with increasing crash prevalence over time

**Expected behavior**: Compute the share of crashes attributed to each contributing factor per year, and identify factors where this share consistently increases across multiple years, not factors with the highest total occurrence count.

#### Prompt-mediated SQL
```sql
WITH factor_crash_counts AS (
    SELECT
        crash_date,
        contributing_factor_vehicle_1 AS contributing_factor,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE contributing_factor_vehicle_1 IS NOT NULL
    GROUP BY crash_date, contributing_factor_vehicle_1
    UNION ALL
    SELECT
        crash_date,
        contributing_factor_vehicle_2 AS contributing_factor,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE contributing_factor_vehicle_2 IS NOT NULL
    GROUP BY crash_date, contributing_factor_vehicle_2
    UNION ALL
    SELECT
        crash_date,
        contributing_factor_vehicle_3 AS contributing_factor,
        COUNT(collision_id) AS crash_count
    FROM crashes
    WHERE contributing_factor_vehicle_3 IS NOT NULL
    GROUP BY crash_date, contributing_factor_vehicle_3
),
factor_trends AS (
    SELECT
        contributing_factor,
        EXTRACT(YEAR FROM TO_DATE(crash_date, 'YYYY-MM-DD')) AS year,
        SUM(crash_count) AS total_crashes
    FROM factor_crash_counts
    GROUP BY contributing_factor, year
),
factor_growth AS (
    SELECT
        contributing_factor,
        year,
        total_crashes,
        LAG(total_crashes) OVER (PARTITION BY contributing_factor ORDER BY year) AS previous_year_crashes
    FROM factor_trends
)
SELECT
    contributing_factor,
    year,
    total_crashes,
    previous_year_crashes
FROM factor_growth
WHERE previous_year_crashes IS NOT NULL AND total_crashes > previous_year_crashes
ORDER BY contributing_factor, year;
```

**PM Verdict**: `partial`  **Notes**: Uses some temporal, repeated-event, or process signal but misses an essential process component.

#### Planner-enforced SQL
```sql
WITH monthly_factors AS (
    SELECT 
        DATE_TRUNC('month', crash_date) AS period,
        contributing_factor_vehicle_1 AS factor,
        COUNT(collision_id) AS crash_count
    FROM 
        crashes
    WHERE 
        contributing_factor_vehicle_1 IS NOT NULL
    GROUP BY 
        period, factor
),
factor_trends AS (
    SELECT 
        factor,
        period,
        crash_count,
        LAG(crash_count) OVER (PARTITION BY factor ORDER BY period) AS previous_crash_count
    FROM 
        monthly_factors
)
SELECT 
    factor,
    period,
    crash_count,
    previous_crash_count
FROM 
    factor_trends
WHERE 
    previous_crash_count IS NOT NULL AND
    crash_count > previous_crash_count
ORDER BY 
    factor, period;
```

**Planner Verdict**: `correct`  **Notes**: Models the required temporal/event-history process pattern.

---

### public_safety_053 — quantitative_misinterpretation (medium)

**Intent**: Vehicle types with highest injury rate per crash involvement

**Expected behavior**: Compute average total persons injured per crash for crashes involving each vehicle type, then rank vehicle types by this per-crash rate, not by the raw total injury count across all crashes involving that type.

#### Prompt-mediated SQL
```sql
SELECT 
    vehicle_type_code_1 AS vehicle_type,
    CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) AS injury_rate
FROM 
    crashes
WHERE 
    vehicle_type_code_1 IS NOT NULL
GROUP BY 
    vehicle_type_code_1
ORDER BY 
    injury_rate DESC
LIMIT 1;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       CAST(SUM(number_of_persons_injured) AS FLOAT) / COUNT(collision_id) AS injury_rate
FROM crashes
WHERE vehicle_type_code_1 IS NOT NULL
GROUP BY vehicle_type_code_1
ORDER BY injury_rate DESC
LIMIT 1;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### public_safety_054 — quantitative_misinterpretation (medium)

**Intent**: Contributing factors with highest lethality ratio

**Expected behavior**: Compute the lethality ratio as number_of_persons_killed / (number_of_persons_killed + number_of_persons_injured) per contributing factor, then rank by this ratio. Factors in fewer but more lethal crashes would otherwise be obscured by high-frequency low-lethality ones.

#### Prompt-mediated SQL
```sql
SELECT 
    contributing_factor_vehicle_1 AS contributing_factor,
    CAST(SUM(number_of_persons_killed) AS FLOAT) / NULLIF(SUM(number_of_persons_injured + number_of_persons_killed), 0) AS lethality_ratio
FROM 
    crashes
WHERE 
    contributing_factor_vehicle_1 IS NOT NULL
GROUP BY 
    contributing_factor_vehicle_1
ORDER BY 
    lethality_ratio DESC
LIMIT 1;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT contributing_factor, 
       CAST(SUM(number_of_persons_killed) AS FLOAT) / COUNT(collision_id) AS lethality_ratio
FROM (
    SELECT contributing_factor_vehicle_1 AS contributing_factor, number_of_persons_killed, collision_id FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_2 AS contributing_factor, number_of_persons_killed, collision_id FROM crashes
    UNION ALL
    SELECT contributing_factor_vehicle_3 AS contributing_factor, number_of_persons_killed, collision_id FROM crashes
) AS factors
WHERE contributing_factor IS NOT NULL
GROUP BY contributing_factor
ORDER BY lethality_ratio DESC
LIMIT 1;
```

**Planner Verdict**: `partial`  **Notes**: Captures a related quantitative signal or proxy, but misses the exact derived measure, scope, or denominator.

---

### public_safety_055 — quantitative_misinterpretation (medium)

**Intent**: Time slots with highest pedestrian-to-motorist injury ratio

**Expected behavior**: Compute the ratio of total pedestrian injuries to total motorist injuries per hour of day, and rank hours by this ratio to identify when pedestrians bear a disproportionate share of injury risk relative to motorists.

#### Prompt-mediated SQL
```sql
SELECT 
    crash_time,
    CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / NULLIF(SUM(number_of_motorist_injured), 0) AS pedestrian_to_motorist_injury_ratio
FROM 
    crashes
GROUP BY 
    crash_time
ORDER BY 
    pedestrian_to_motorist_injury_ratio DESC
LIMIT 1;
```

**PM Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

#### Planner-enforced SQL
```sql
SELECT crash_time, 
       CAST(SUM(number_of_pedestrians_injured) AS FLOAT) / NULLIF(SUM(number_of_motorist_injured), 0) AS pedestrian_to_motorist_injury_ratio
FROM crashes
GROUP BY crash_time
ORDER BY pedestrian_to_motorist_injury_ratio DESC
LIMIT 1;
```

**Planner Verdict**: `correct`  **Notes**: Computes the intended derived quantitative measure or ratio.

---

### public_safety_060 — role_confusion (medium)

**Intent**: Boroughs with worst pedestrian safety record

**Expected behavior**: Pedestrian safety should be measured by pedestrian injuries per crash (or per unit of exposure), not total pedestrian injury count. Boroughs with more crashes would otherwise rank worst purely because of volume, masking genuine rate differences.

#### Prompt-mediated SQL
```sql
SELECT 
    borough, 
    SUM(number_of_pedestrians_injured) AS total_pedestrians_injured,
    SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM 
    crashes
GROUP BY 
    borough
ORDER BY 
    total_pedestrians_killed DESC, 
    total_pedestrians_injured DESC;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT borough, 
       SUM(number_of_pedestrians_injured) AS total_pedestrians_injured, 
       SUM(number_of_pedestrians_killed) AS total_pedestrians_killed
FROM crashes
GROUP BY borough
ORDER BY total_pedestrians_killed DESC, total_pedestrians_injured DESC;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### public_safety_061 — role_confusion (medium)

**Intent**: Streets with most dangerous conditions

**Expected behavior**: Street danger should reflect injury or fatality rate per crash on that street, not raw collision count. A busy intersection with many low-severity crashes is less dangerous than one with fewer but consistently severe crashes.

#### Prompt-mediated SQL
```sql
SELECT 
    on_street_name, 
    cross_street_name,
    SUM(number_of_persons_injured + number_of_persons_killed) AS total_casualties
FROM 
    crashes
GROUP BY 
    on_street_name, 
    cross_street_name
ORDER BY 
    total_casualties DESC
LIMIT 10;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT borough, 
       SUM(number_of_persons_injured + number_of_persons_killed) AS total_casualties
FROM crashes
GROUP BY borough
ORDER BY total_casualties DESC
LIMIT 10;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---

### public_safety_062 — role_confusion (medium)

**Intent**: Vehicle types most responsible for cyclist injuries

**Expected behavior**: Responsibility for cyclist injuries should be measured by the average number of cyclists injured per crash where the vehicle type appears, not the total number of crashes or total cyclist injuries — common vehicle types would otherwise dominate by volume.

#### Prompt-mediated SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       SUM(number_of_cyclist_injured) AS total_cyclist_injuries
FROM crashes
GROUP BY vehicle_type_code_1
ORDER BY total_cyclist_injuries DESC
LIMIT 1;
```

**PM Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

#### Planner-enforced SQL
```sql
SELECT vehicle_type_code_1 AS vehicle_type, 
       SUM(number_of_cyclist_injured) AS total_cyclist_injuries
FROM crashes
GROUP BY vehicle_type_code_1
ORDER BY total_cyclist_injuries DESC
LIMIT 1;
```

**Planner Verdict**: `partial`  **Notes**: Avoids clearly invalid role usage or provides a meaningful proxy, but the underspecified role concept remains only partially grounded.

---
