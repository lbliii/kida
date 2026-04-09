Fix `~` operator to preserve `Markup` safety — `code(x) ~ " " ~ copy_button(x)` no longer double-escapes HTML. Also fixes the `+` operator's string concatenation branch.
