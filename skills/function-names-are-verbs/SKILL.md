---
name: function-names-are-verbs
description: Name every function with a verb, because a function is an action. Use when naming or renaming a function, method, hook callback or handler, when a function name is a noun such as `data`, `result`, `userValidation` or `payment`, when reviewing new code for naming, or when the user asks what to call a function.
---

# Function names are verbs

A function does something. Its name must say what it does. **Start every
function name with a verb.**

- `validate_payment` — not `payment_validation`.
- `buildInvoice` — not `invoiceBuilder`.
- `fetchUser` — not `userData`.
- `retryUpload` — not `uploadRetry`.

A noun names a thing. Classes, variables, types, modules and files are things.
Functions are not.

## Not optional

This rule is required. It is not a style preference.

No hook enforces it, so nothing will stop you from skipping it. That makes it
easier to drop under time pressure, not less binding.

## The test

Read the name aloud with a subject in front of it: "it ____". If the sentence
works, the name is a verb.

- "it validates payment" — good.
- "it payment validation" — not a function name.

## Booleans are still verbs

`is`, `has`, `can`, `should` and `needs` are verbs. Use them.

- `isEligibleForRefund`, `hasActiveSubscription`, `canDeleteOrder`.
- Not `eligibility`, not `activeSubscription`, not `deletable`.

## Pick the verb that is true

The verb carries the contract. A wrong verb is worse than a noun.

- `get` returns something cheap and already present.
- `fetch` or `load` crosses a network or a disk.
- `build`, `create`, `make` return a new value.
- `update`, `set`, `apply` change state.
- `ensure` makes a condition true and is safe to call twice.

`handle`, `process` and `manage` are weak. They fit anything, so they stay true
however much the function grows. Prefer the specific verb when one exists:
`chargeOrder` over `processOrder`. When you keep the weak verb, check the length
— see the `oversized-function` skill.

## The exceptions

- **Components.** A React, Vue or Svelte component is a function, but it names a
  thing on screen. `UserCard`, `CheckoutForm`. Keep the noun.
- **Python `@property`.** A property is read like an attribute. `total_price`,
  not `get_total_price`.
- **Constructors and factories that carry a type name.** `Money.of`, `User.from_row`.

Nothing else. A callback is a function: `onSubmit` is a field, but the function
behind it is `submitOrder`, never `submitHandler`.

## Applying this

- The verb comes first. Then the object it acts on.
- One verb per name. Two verbs means two functions.
- Keep the name inside ten words — see the `self-documenting-names` skill.
