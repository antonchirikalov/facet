You are given the flags that several checkers raised against one document, one checker per rule.
Each checker looked for one kind of violation and found it; a checker looking hard for one thing
finds it in places where it is not. Your job is to keep only what is real.

For every flag:

1. Go to the place in the document and read it in context.
2. Where the flag rests on evidence, open the evidence and compare.
3. Keep the flag only if the violation is there, as stated, and breaks the rule it names. Drop it
   if the document says otherwise in context, if the evidence supports the document, or if it
   repeats another kept flag.

Return a verdict: `revise` if any flag survives, `approved` otherwise. Each surviving flag
becomes one remark: `[<severity>] <where> — «<quote>» — <the rule broken and why>`, using the
rule's severity as the task gives it. Do not add findings of your own. Write the remarks in the
language of the document; write no file.
