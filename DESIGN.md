# Mascot Design Specification

## 1. Product Identity

Mascot is an AI-powered English vocabulary learning product for university students and young professionals.

The product should feel:
- youthful
- modern
- intelligent
- friendly
- visually appealing
- polished like a real startup product

It must NOT feel:
- childish
- cartoon-heavy
- overly gamified
- corporate
- textbook-like
- old-fashioned
- like an admin dashboard
- like a Bootstrap template
- visually generic

Visual direction:

Modern EdTech + soft playful + premium SaaS.

---

## 2. Brand

Primary direction:
- purple / indigo
- soft neutral / lavender backgrounds
- white cards and surfaces
- dark navy primary text
- muted gray secondary text

Primary mascot identity:
- a minimal geometric penguin inside a rounded-square indigo badge
- dark navy body, white face/belly, soft lavender details, and one restrained sparkle
- reusable as the sidebar mark, SVG favicon, authentication visual, learner-home support visual, empty state, and completion mark
- friendly and intelligent without baby-like proportions, detailed cartoon styling, or clipart treatment

AI-related features should have a subtle distinct identity using:
- violet gradient
- sparkle motif
- AI badge

Do not use gradients throughout the whole product.

Avoid:
- neon
- excessive pastel colors
- heavy glassmorphism
- excessive shadows
- rainbow interfaces

---

## 3. Typography

Preferred font:
Plus Jakarta Sans

Fallback:
Inter / modern sans-serif

Hierarchy:

Display:
- 40-48px
- bold

Page title:
- 28-32px
- 700

Section title:
- 18-22px
- 600-700

Body:
- 15-16px
- 400-500

Secondary text:
- 13-14px

Use strong hierarchy and generous readability.

---

## 4. Spacing

Use an 8px-based spacing system.

Preferred values:

4
8
12
16
24
32
48
64

Typical usage:

Card padding:
24px

Section spacing:
32px

Form field spacing:
16px

Do not use arbitrary spacing values unless necessary.

---

## 5. Radius

Buttons:
10-12px

Inputs:
10-12px

Normal cards:
14-16px

Hero cards:
20-24px

Modals:
20px

Avoid turning every component into a pill.

---

## 6. Shadows and Borders

Prefer:
- subtle borders
- soft shadows
- restrained elevation

Cards should not use large or dramatic shadows.

The interface should create depth mainly through:
- background contrast
- borders
- spacing
- surface hierarchy

---

## 7. Icons

Use one consistent outline icon system.

Preferred style:
Lucide-like outline icons.

Do not mix:
- emoji
- FontAwesome
- Material icons
- unrelated custom icon styles

Emoji may appear only as very limited content decoration if appropriate.

---

## 8. Desktop Application Shell

Use a persistent left sidebar.

Navigation:

- Dashboard
- Learn
- My Vocabulary
- Review
- Practice

Bottom/sidebar secondary area:

- account information
- logout

Use a spacious main content area.

Application background:
very light neutral / lavender

Sidebar and cards:
white or softly tinted surfaces

---

## 9. Mobile Application Shell

Mobile should not simply shrink desktop.

Use:
- compact top bar
- bottom navigation where appropriate
- stacked content
- touch-friendly actions

Avoid horizontal desktop tables.

---

## 10. Dashboard

The Dashboard is a learner home screen.

It must NOT feel like an analytics/admin dashboard.

The user should immediately understand:

1. What am I learning?
2. What should I do next?
3. How am I progressing?

Structure:

- welcome header
- dominant learning journey hero
- current General English / CEFR journey
- current topic or vocabulary set
- learning progress
- Continue Learning CTA
- vocabulary learned
- due-for-review count
- exercise accuracy
- Review CTA
- Practice CTA
- recent vocabulary

The learner-home hierarchy is intentionally limited to one dominant journey hero, three actionable next-step cards (Review, Practice, Add vocabulary), three lightweight progress numbers, and six recent vocabulary items in a balanced two-column layout. The hero keeps the penguin but removes any separate vocabulary-mastery box. Detailed status and attempt breakdown panels must not compete with the next action.

Do not let metric cards dominate the page.

Avoid complex business charts.

---

## 11. Learn

Learn should feel like content discovery.

Structure:

- Learn English
- General English track
- CEFR selector:
  A1 A2 B1 B2 C1 C2
- vocabulary topic cards

Examples:
- Daily Life
- Family
- Travel
- Work
- Education
- Communication
- Work & Business
- Technology

Each topic card may show:
- title
- CEFR
- word count
- progress
- Start / Continue action
- subtle topic visual or icon

Do not display vocabulary sets like CRUD tables.

---

## 12. Vocabulary Set Detail

This screen should feel like selecting learning content.

Show:
- back navigation
- topic
- CEFR
- word count
- progress
- Select All
- selectable vocabulary items
- Add Selected Words CTA

Each word may display:
- word
- part of speech
- concise definition
- Vietnamese translation
- CEFR
- Already Learning state

Already-learning words should be visually clear and non-selectable where appropriate.

---

## 13. My Vocabulary

My Vocabulary should feel like a personal learning library.

Do not make it look primarily like CRUD management.

Include:
- search
- CEFR filter
- status filter
- topic filter
- Add Vocabulary CTA

Prioritize:
- word
- part of speech
- definition
- translation
- CEFR
- learning status
- topic

Edit/Delete must remain secondary actions.

Learning statuses:

- New
- Learning
- Review
- Mastered

Use clear but restrained badges.

---

## 14. AI Vocabulary Assistant

This is one of Mascot's signature interactions.

Flow:

word input
→ Generate with AI
→ loading
→ AI preview
→ editable fields
→ explicit user confirmation
→ Save

AI-generated fields:
- word
- part of speech
- English definition
- Vietnamese translation
- CEFR estimate
- exactly one example sentence

AI UI identity:
- sparkle icon
- subtle violet gradient
- Mascot AI badge

AI output must look editable and reviewable.

Never visually imply that AI automatically saves data.

---

## 14.1 Topic and Duplicate Interactions

Topic fields in Add Vocabulary, Edit Vocabulary, and relevant My Vocabulary filters use an accessible autocomplete/typeahead combobox.

The combobox should:
- show database-backed personal suggestions on focus
- filter case-insensitively after a short debounce
- prioritize prefix matches
- support Arrow Up, Arrow Down, Enter, and Escape
- provide loading and no-result states
- allow `Create “topic”` in vocabulary forms when there is no exact match

My Vocabulary includes a lightweight Manage Topics modal, not a separate administration page. It shows personal topic counts and supports inline rename plus a clear confirmation before removal. Removing a topic must explain that vocabulary remains and only its topic field is cleared.

Duplicate-sense conflicts use a restrained warning state near the form actions. The message should explain that the word has the same or overlapping meaning and, when available, offer a clear `View existing word` action. Never overwrite an existing entry automatically.

---

## 15. Review

Review should feel immersive and focused.

One word at a time.

Use a large flashcard.

Before reveal:
- progress
- CEFR
- word
- part of speech
- Reveal Meaning

After reveal:
- English definition
- Vietnamese translation
- example sentence
- Didn't Know
- Got It

Keep surrounding UI minimal.

Completion state:
- reviewed words
- correct
- incorrect
- accuracy
- Dashboard / Practice CTA

---

## 16. Practice

Practice should feel like a focused learning session.

Setup:
- Step 1 — vocabulary source selector: Recent words, By topic, or Custom selection
- Step 2 — current supported exercise type
- Step 3 — number of questions for Multiple Choice, or the fixed `1 passage · 4 blanks` summary for Fill in the Blank
- Step 4 — Generate with AI

Show only controls relevant to the selected source mode. Recent words requires no checkboxes. By topic reuses the personal topic typeahead without topic mutation. Custom selection uses a scrollable checklist with Select All, Clear selection, and selected count.

Always show a contextual source summary such as `Using 15 recent words`, `Work · 12 words available`, or `8 words selected`. Visually distinguish the vocabulary source-pool size from the output question count.

Multiple Choice count defaults to 5 and accepts 1–15. Its controlled edit state must allow a temporary blank value while typing; validate on blur or generation instead of coercing every keystroke. Fill in the Blank hides/disables that count control and clearly states `1 passage · 4 blanks`.

Select All means all eligible vocabulary becomes source material. It must never change the requested question count or imply one generated question per selected word. Four-option multiple choice should show a friendly minimum requirement of four distinct eligible words.

The setup surface should remain mostly neutral/white. Reserve the violet gradient and sparkle treatment for the AI generation action rather than tinting the entire container.

Multiple Choice screen:
- Question X of Y and progress bar
- one complete contextual English sentence with exactly one blank
- four large A/B/C/D English vocabulary answer cards
- Submit, then Correct/Not quite, correct option, concise explanation, and Next Question

Fill in the Blank screen:
- one coherent titled 4–5 line passage containing `(1) ______` through `(4) ______`
- four numbered question groups below the passage
- four A/B/C/D options for every blank
- one final submission for all four answers; unanswered blanks prevent submission
- after submission, show total score plus correct/incorrect state, correct option, and concise explanation for each blank

Never present the primary V1 formats as definition-to-word multiple choice or as a one-sentence free-text blank.

Feedback:
- Correct / Incorrect
- correct answer
- concise explanation
- Next Question

Completion:
- score
- accuracy
- vocabulary needing review
- Practice Again
- Back to Dashboard

Gamification should be light.

---

## 17. Authentication

Login and Register should feel polished and modern.

May use:
- split-screen layout
- subtle Mascot illustration / abstract motif
- branded background treatment

Include:

Mascot

"Learn smarter, one word at a time."

Do not add unsupported features such as social login.

---

## 18. System States

Every important screen should support:

Loading:
- skeletons instead of plain "Loading..."

Empty:
- helpful explanation
- useful next action

Error:
- clear friendly message
- retry action where appropriate

Do not expose raw backend errors or stack traces.

---

## 19. Interaction

Use subtle micro-interactions:

- button hover
- card hover
- active sidebar transition
- progress transition
- flashcard reveal
- skeleton loading

Avoid:
- heavy animation
- constant motion
- page flying effects
- unnecessary confetti

---

## 20. Mascot Visual Motif

A subtle abstract mascot or friendly visual motif may appear in:

- authentication
- Dashboard hero
- empty states
- completion screens

Do not create a cartoon-heavy experience.

The visual should support the brand, not dominate it.

---

## 21. Development Rules

UI redesign must NOT change:

- backend APIs
- database schema
- authentication behavior
- vocabulary business rules
- review scheduling
- Groq integration
- structured AI output behavior
- exercise generation logic
- deterministic grading
- dashboard calculations

Reuse existing frontend logic.

Avoid unrelated refactors.

---

## 22. Design Priority

When rules conflict, prioritize:

1. usability
2. learning clarity
3. consistency
4. accessibility
5. visual polish
6. decoration

Product consistency is more important than visual novelty.

---

## 23. Vietnamese Interface and Visual Composition

The V1 product shell and all interface controls use natural professional Vietnamese. English remains only where it is the learning content itself, such as vocabulary, example sentences, exercise passages, CEFR labels, and answer options. Exercise explanations and feedback are Vietnamese.

Main pages share one header rhythm: a visible purple uppercase eyebrow, a strong 34–48px title, concise supporting copy, consistent content width, and optional restrained learning illustration. Desktop keeps the white persistent sidebar against a light lavender-gray application background.

The Learn page uses an illustrated discovery hero, a six-option CEFR selector, and compact topic cards with restrained purple, pink, teal, or amber accents. Practice uses a compact four-step setup, contextual current-session progress, and a completion surface with score, accuracy, correct/incorrect summary, and question review. Historical legacy exercises must never be merged into a newly generated active session.
