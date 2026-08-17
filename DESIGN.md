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
- exercise type
- number of questions
- vocabulary source
- AI generation action

Question screen:
- Question X of Y
- progress bar
- large readable prompt
- answer cards or fill-in input
- Submit

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
