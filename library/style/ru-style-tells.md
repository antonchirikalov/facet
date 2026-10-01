# Russian material for the style critic

Data, not a prompt. The critic `style_critic_ru` reads this file at the start of its work: it
holds everything the critic looks for in Russian text and cannot name in English. The critic's
prompt is entirely in English and points here. Edited by hand, like the voice profile.

The Russian words and phrases below are examples to match in Russian text; they are kept
verbatim on purpose.

## Forms of address (mixing formal "вы" and informal "ты" is a defect)

тебе, тебя, твой, твоя, твои, твоё, ты

## Clichés

The main list is `library/style/forbid/ru-slop.txt`, one regex per line; the gate uses it too.
This section holds what a regex cannot catch.

Anglicism verbs that have an exact Russian verb:
«валидирует» → «проверяет», «имплементирует» → «реализует», «хендлит» → «обрабатывает»,
«репортит» → «сообщает». Leave the nouns that are terms alone («валидация», «имплементация»
as the name of a mechanism), especially when a figure fixes them.

Authorial transitions that stay: «Давайте разбираться», «А давайте пример».
The defect is «давайте разберём каждый пункт подробнее», where the word stands in for a
thought.

## Tells of generated text, with examples

- A heading that names instead of promising: «Формула целиком» names the topic; «Что на что
  умножается» promises work.
- Bold used as a table of contents inside a paragraph: `**QKᵀ.** Скалярное произведение…`
- Connective adverbs opening consecutive paragraphs: «Однако», «Кроме того», «При этом»,
  «Более того».
- Impersonal passive with an inanimate agent: «кейсы разбираются», «валидация выполняется».
  Rewrite with a living agent, usually "вы" or the imperative.
- The chain "не X, а Y" twice in a row, and the form «это не просто X — это Y».
- Intensifying triads: «быстро, надёжно и масштабируемо».
- Quotes: `"…"` around Russian prose → «…»; nested quotes → „…“.
- A list marker `- пункт` at the start of a line is not a hyphen standing in for a dash.

## Calibration: what a good edit looks like

Before: «Кейсы, где агент провалился, разбираются и пополняют датасет; трассы с плохими
отзывами - туда же.»
After: «Разбирайте кейсы, где агент ошибся, и добавляйте их в датасет — вместе с
трассами, на которые пожаловались пользователи.»
(one agent, active voice, one dash, about the same length)
