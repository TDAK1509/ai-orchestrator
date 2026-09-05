---
name: maintainable-coding-principles
description: Seven habits for writing code that is easier to understand, change, test, debug, and trust - visible main paths, meaningful names, contained external dependencies, invalid states made unrepresentable, decisions separated from side effects, useful errors, and focused changes. Use whenever you write, edit or review code, before you start an implementation, or when the user asks how to make code more maintainable.
---

# Maintainable coding principles

> Make the next change easier.

Better engineering is not necessarily about writing more sophisticated code.
Experienced engineers make important logic obvious, constrain invalid states,
isolate complexity, and keep changes focused.

These are heuristics, not laws. Do not mechanically replace every nested
condition with an early return, wrap every dependency in an adapter, split
every function into fragments, or invent elaborate types for trivial state.
The question is always: does this make the code easier for the next engineer
to understand, safely change, test, and trust?

## 1. Keep the main path easy to follow

Prefer guard clauses and early returns when they make the successful path
easier to see.

```ts
// Weaker: the operation is buried inside nested ifs.
async function processUser(userId: string) {
  const user = await getUser(userId)
  if (user) {
    if (user.active) {
      if (user.canCheckout) {
        return createCheckout(user)
      }
    }
  }
  throw new Error("Cannot checkout")
}

// Better: guard clauses, main path visible.
async function processUser(userId: string) {
  const user = await getUser(userId)
  if (!user) throw new Error("User not found")
  if (!user.active) throw new Error("User inactive")
  if (!user.canCheckout) throw new Error("Checkout not allowed")
  return createCheckout(user)
}
```

Do not blindly eliminate all nesting. Keep the important path of the function
easy to follow — that is the goal, not zero indentation.

## 2. Name things by meaning

Prefer names that communicate domain or business meaning over generic names
such as `data`, `item`, `result`, `value`, or `obj`.

```ts
// Weaker
const data = await getData()
for (const item of data) {
  const result = calculate(item)
  await save(result)
}

// Better
const pendingOrders = await getPendingOrders()
for (const order of pendingOrders) {
  const invoice = createInvoice(order)
  await saveInvoice(invoice)
}
```

Names should reduce detective work. They do not need to be long; the
important concept should be obvious.

## 3. Keep external systems behind a boundary

Do not let third-party API types, field names, and response shapes spread
through domain logic — Stripe, email providers, storage, AI providers, and
similar.

```ts
// Weaker: application code depends on Stripe's own shape.
function sendInvoice(customer: Stripe.Customer) {
  sendEmail(customer.email!)
}

// Better: convert at the boundary, use an internal model.
type Customer = { id: string; email: string; companyName: string }

function fromStripeCustomer(c: Stripe.Customer): Customer {
  return { id: c.id, email: c.email ?? "", companyName: c.metadata.company_name ?? "" }
}

function sendInvoice(customer: Customer) {
  sendEmail(customer.email)
}
```

A possible layout: `stripe/stripe-client.ts`, `stripe/stripe-adapter.ts`,
`domain/customer.ts`. If a provider changes its representation, ideally only
the adapter changes.

Do not introduce this for trivial integrations — use it when it meaningfully
prevents external details from leaking through the codebase.

## 4. Make invalid states harder to represent

Avoid models where many fields are optional merely because they are valid in
some states.

```ts
// Weaker: permits a "paid" order with no payment info.
type Order = {
  id: string
  status: "pending" | "paid"
  paymentId?: string
  paidAt?: Date
}

// Better: each state carries only the fields it needs.
type PendingOrder = { id: string; status: "pending" }
type PaidOrder = { id: string; status: "paid"; paymentId: string; paidAt: Date }
type Order = PendingOrder | PaidOrder
```

Instead of repeatedly writing `if (!order.paymentId) throw ...`, design the
state so a paid order cannot exist without a payment ID. Use discriminated
unions or an equivalent pattern when practical.

## 5. Separate decisions from actions

Keep important business decisions separate from side effects — database
writes, emails, network calls, analytics, payment operations.

```ts
// Weaker: eligibility logic mixed with DB and email calls.
async function activateFeature(user: User) {
  if (user.age >= 18 && user.emailVerified && !user.banned) {
    await db.users.update(user.id, { featureEnabled: true })
    await sendEmail(user.email, "Feature enabled")
  }
}

// Better: the decision is a pure, testable function.
function canUseFeature(user: User): boolean {
  return user.age >= 18 && user.emailVerified && !user.banned
}

async function activateFeature(user: User) {
  if (!canUseFeature(user)) return
  await db.users.update(user.id, { featureEnabled: true })
  await sendEmail(user.email, "Feature enabled")
}
```

`canUseFeature` is now testable with no database or email mocks. Apply this
to permissions, pricing, validation, eligibility, retries, and notifications.

## 6. Make errors useful

Errors should help both humans and software understand what happened.

```ts
// Weaker: the caller cannot distinguish failure kinds.
throw new Error("Something went wrong")

// Better: a stable code plus a human message.
class AppError extends Error {
  constructor(public code: string, message: string, public context?: Record<string, unknown>) {
    super(message)
  }
}

throw new AppError("PAYMENT_DECLINED", "The payment was declined", { orderId: order.id })
```

Callers branch on `error.code`, not on parsing `error.message`. Logs should
carry safe diagnostic context (`errorCode`, `orderId`, `userId`). Never log
secrets: passwords, access tokens, API keys, or other credentials.

## 7. Keep changes focused

This applies to commits and pull requests as much as to code.

A PR titled "Improve checkout" that also refactors the Stripe service,
renames `User` to `Account`, upgrades Tailwind, and fixes an unrelated email
bug is hard to review, test, and revert — even if every change is correct.

Prefer one focused PR per concern, and commits with a clear single purpose
(`feat: add checkout eligibility rule`, not `fix stuff`). Focused changes are
easier to review, test, understand, debug, revert, cherry-pick, and bisect.
See `increments-plan` for splitting work into focused PRs before you start.

## Review checklist

Before finishing a coding task, ask:

- Can the main execution path be understood quickly? Any unnecessary nesting?
- Do names communicate business/domain meaning?
- Are third-party implementation details leaking into unrelated code?
- Can invalid states be constructed unnecessarily?
- Are important business decisions mixed with side effects? Can the decision
  be tested independently?
- Are errors machine-readable (stable codes) and useful to humans?
- Do logs carry enough safe diagnostic context, with no secrets in them?
- Did the change introduce unrelated refactoring or cleanup?
- Is the next developer's change easier or harder because of this
  implementation?
