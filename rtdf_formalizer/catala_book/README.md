# Catala 1.2 tutorial and language reference

This is the task-relevant subset of the [Catala book](https://github.com/CatalaLang/catala-book)
at tag `1.2.0` (commit `3535509eeb4e05208744a0bd22819a91840f7987`),
which matches this repository's Catala 1.2.1 toolchain. The upstream Markdown
is retained except for references to omitted French, exercise, and external
example-program material.

## Included tutorial material

- [Tutorial overview](src/2-0-tutorial.md): the running income-tax example
  and the recommended order for the tutorial chapters.
- [Basic blocks](src/2-1-basic-blocks.md): literate law-and-code documents,
  structures, enumerations, scope declarations, variable definitions, numeric
  and date values, formulas, typechecking, and input-free test scopes.
- [Conditional definitions and exceptions](src/2-2-conditionals-exceptions.md):
  conditions, base definitions, prioritized exceptions, exception trees, and
  grouping related definitions.
- [Lists and scopes](src/2-3-list-scopes.md): list construction and mapping,
  decomposing computations into scopes, and static sub-scope calls.
- [Variable states and dynamic scope calls](src/2-4-states-dynamic.md):
  multi-state variables, dynamic scope mapping over lists, traces, and debugging.

## Included Catala-specific FAQ

- [Catala-specific questions](src/4-2-catala-specific.md): practical guidance
  on choosing `condition` and `rule` instead of ordinary booleans; explicit
  numeric casts; money representation and rounding; arbitrary-precision
  integers and decimals; constructing and computing with dates and durations;
  modeling domains without strings; adding exceptions through context
  variables; updating structures; supported compilation targets; and why scope
  declarations, unlike scope definitions, cannot be split across files.

## Included language reference material

- [Literate programming and basic syntax](src/5-1-literate-programming.md):
  free text, headings, Catala fences, comments, keywords, Markdown extensions,
  weaving, tangling, and textual inclusion.
- [Types, values, and operations](src/5-2-types.md): booleans, integers,
  decimals, money, dates, durations, casts, structures, enumerations, lists,
  tuples, optional values, functions, and polymorphic functions.
- [Scopes, functions, and constants](src/5-3-scopes-toplevel.md): scope inputs,
  context and output variables, states, conditions, sub-scopes, output
  structures, and top-level constants and functions.
- [Definitions and exceptions](src/5-4-definitions-exceptions.md): ordinary
  and conditional definitions, states, conditions, exception priorities,
  sub-scope binding, assertions, and date-rounding modes.
- [Expressions](src/5-5-expressions.md): references, operators, local
  bindings, conditionals, constructors, pattern matching, collection and tuple
  expressions, function and direct scope calls, impossible cases, and assertions.
- [Modules](src/5-6-modules.md): module declarations, imports, visibility,
  public interfaces, and source-file inclusion.
- [Standard library](src/5-7-standard-library.md): the `Integer`, `Decimal`,
  `Money`, `Duration`, `Date`, `MonthYear`, `Period`, and `List` modules.

The book text is licensed under CC BY 4.0; see [`LICENCE.txt`](LICENCE.txt).
