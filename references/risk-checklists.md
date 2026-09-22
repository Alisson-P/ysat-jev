# Risk checklists by domain

A sweep list, not a questionnaire. Do not answer all of these in the output: use the list to find
the category that would otherwise be missed, and carry into the analysis only what has evidence or
is materially risky. The final answer stays capped at `max_risks`.

Domains set in `focus_domains` are swept first and in depth. Every other domain still gets a fast
pass, because the missed risk is almost always in the category nobody assigned to themselves.

## 1. Architecture and cloud

- What does this decision lock in permanently (data format, region, SKU, identity model)?
- Is there a service limit, quota or throttling threshold that only shows up at production scale?
- Which component becomes a single point of failure after the change?
- Does the decision assume an availability or latency figure that nobody measured?
- Does a rollback exist, has it been tested, and how long does it take?

## 2. Security and identity

- Who gains access they did not have? Does any permission become permanent?
- Does the change create a new credential, key or secret? Where does it live?
- Does it add public exposure, a new endpoint or a new tunnel?
- Does an existing control (multifactor, conditional access, endpoint protection, data loss
  prevention, logging) sit outside the new path?
- Does the audit trail stay complete after the change?

## 3. Data and privacy

- Does data cross a boundary it does not cross today (region, tenant, vendor, country)?
- Is there a migration with no way back? Was the backup validated by a restore, not just by existing?
- Do retention, classification and labelling survive at the destination?
- Does anyone depend on a report, export or integration that breaks silently?

## 4. Cost and licensing

- Which variable does the cost grow with? What happens at peak and at year end?
- Is a licence, SKU or add on required that nobody budgeted?
- Was the pilot cheap because it was small? Redo the arithmetic at real volume.
- Exit cost: how much does it cost to walk away from this choice later?

## 5. Operations and support

- Who operates this day to day, and do they know they will?
- Do monitoring and alerting cover the new path, or only the old one?
- Do a runbook, documentation and handover exist before go live?
- Who answers out of hours? Does the vendor SLA match what was promised to the client?

## 6. Delivery and schedule

- Does the deadline assume nothing goes wrong? Where is the slack?
- How many external dependencies have to land on time for that date to hold?
- Do holidays, vacations, a change freeze or the client's maintenance window sit in the path?
- Does this delay something already promised in writing?

## 7. Vendor and contract

- Is the capability in the contract, or only on the sales slide?
- Is there lock in, a penalty, a minimum term or an automatic renewal?
- Is the product in preview, deprecated, or with an announced end of support?
- What happens if the vendor changes price, model or roadmap within twelve months?

## 8. People and process

- Who has to agree and has not been consulted? (frame as role and process, never evaluate a person)
- Does the plan depend on one person holding the knowledge in their head?
- Are training and adoption in the plan, or only the technical work?
- Has this been attempted here before? What stopped it?

## 9. Compliance and regulatory

- Is there a standard, internal policy or client requirement this choice breaches?
- Could a future audit prove what was done, by whom and when?
- Does the decision contradict something stated in a formal document (proposal, statement of work,
  assessment report)?

## 10. Biases that usually prop up the wrong decision

- **Sunk cost**: continuing because of what was already spent, not because it makes sense.
- **Proof by enthusiasm**: the demo worked, therefore production will work.
- **Silent consensus**: nobody objected in the meeting because nobody had the data yet.
- **Inherited urgency**: the date came from an old slide and became law without review.
- **Scope optimism**: the estimate covers the happy path and nothing else.
- **Authority anchor**: it is right because the most senior person in the room said it first.

## 11. Questions that apply to every decision

- What has to be true for this to work, and which of those is least verified?
- What would the strongest opponent of this decision say, and what would they point at?
- What is the cheapest experiment that would settle the main open question this week?
- If this fails, how will we find out: from monitoring, from the client, or from the invoice?
