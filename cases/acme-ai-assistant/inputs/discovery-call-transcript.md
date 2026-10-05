# Discovery call — Acme Clinics, AI patient assistant

Participants (by role):

- COO, Acme Clinics (COO)
- Medical Director, Gastroenterology (MD)
- Head of IT (IT)
- Data Protection Officer (DPO)
- Front-desk team lead, Munich site (FD)
- Vendor: solution architect (SA), account lead (AL)

Duration: 58 minutes. Transcript lightly edited for readability.

---

[00:00:40] AL: Thanks for making the time. We read the RFP; today we would like to understand
how things work at the front desk and what would make this a success for you.

[00:01:15] COO: Short version: our front desks are drowning. I want the assistant to take the
written traffic off them. If it can handle booking end to end without anyone touching it, that is
the win. Fully autonomous, that is what I told the board.

[00:02:05] FD: Can I give the reality from Munich? We have four people on the desk in the morning.
The WhatsApp line alone has about three hundred messages waiting on a Monday. Half of them are
"can I move my appointment" and the other half are "do I have to stop my blood thinner before the
colonoscopy". The second kind is the one that scares me, because the answer depends on the
medication and on the doctor.

[00:03:10] MD: That is exactly my concern. The preparation leaflet says what to do in general.
For anticoagulants it says: contact your doctor. I do not want a machine telling a patient on
apixaban when to stop it. That is a clinical decision. If the assistant repeats the leaflet, fine.
If it interprets, no.

[00:04:00] SA: So for medication questions, the assistant can quote the leaflet but must hand over
anything that depends on the individual patient?

[00:04:12] MD: Yes. And it has to be the current leaflet. We change them every month. Last March
we changed the bowel preparation for colonoscopy from a two-day to a one-day regime, and for weeks
patients were still following the old one from a printout.

[00:05:30] COO: Which is why I wrote 100% accuracy in the RFP. If it says something wrong about
preparation, that is a cancelled slot at best and a patient in hospital at worst.

[00:05:50] SA: Understood. I will be honest about one thing: no system that uses a language model
is right every single time. What we can do is measure how often it is right, on your real
questions, make it say only what the leaflet says and show the passage, and make it hand over when
it is not sure. Would that work for you?

[00:06:25] COO: As long as I can show the board a number every month and the number is good. What
does good look like?

[00:06:40] MD: For preparation, I would want ninety-nine out of a hundred answers to be exactly
the leaflet, and the remaining one to be a handover, not a wrong answer.

[00:07:20] SA: Let us talk about booking. What does the desk do today when a patient wants to
move an appointment?

[00:07:35] FD: Find the patient in MediDesk, check the examination type, look for a slot at the
same site or a nearby site, check whether the examination needs a doctor's review, and if it is
less than twenty-four hours, tell them about the fee. Self-payers pay thirty euros, fifty for MRI
and CT. The site manager can waive it, and they do, for example when the patient was in hospital.

[00:08:30] COO: The fee is important. We lose a lot of money on late cancellations. But I do not
want the assistant to argue with patients about it either.

[00:08:45] SA: So the assistant states the fee, books, and if the patient asks for a waiver, it
goes to the site manager?

[00:08:55] COO: Yes. Waivers and refunds are never automatic.

[00:09:40] IT: On MediDesk: the API is fine for reads, but write operations are slower, around two
seconds per booking call, and the rate limit is twenty requests per second for the whole group.
On Monday mornings we already hit it with our own web booking.

[00:10:30] SA: Is there a sandbox?

[00:10:35] IT: There is a test tenant with anonymised data, refreshed quarterly.

[00:11:10] IT: Also, MediDesk goes down. Not often, maybe four or five times a year for an hour or
two, usually on update nights, but once it was a whole Saturday morning.

[00:11:50] COO: On that Saturday we had two hundred patients we could not reach. If the assistant
can at least answer the preparation questions and say "we will confirm your booking shortly", that
is already better than today.

[00:13:00] SA: Who should the assistant hand over to, and what happens out of hours?

[00:13:15] FD: The desk queue during opening hours. Out of hours, nobody. We open at seven.

[00:13:30] MD: Unless it is clinical and urgent. Chest pain, bleeding after a procedure, a severe
reaction to contrast. Those people must be told to call 112 or go to the emergency department, and
at the same time the message must be flagged for the on-call doctor of the site. We have on-call
doctors for procedures done that day.

[00:14:20] SA: How often do you see those messages today?

[00:14:30] FD: In Munich, maybe two or three a week in writing. Mostly after colonoscopies.

[00:15:40] DPO: May I come in on data. Health data, two countries, Article 9. A few things I need
to see in the design. One: everything stays in the EU, including the language model. Two: no
training on our data, in writing from every subprocessor. Three: the assistant must not see more
of the patient record than it needs. If it is moving an appointment, it does not need the
diagnosis.

[00:16:35] SA: Does the copilot for the desk need the clinical record?

[00:16:45] DPO: It needs the contact history and the appointments. Not findings, not reports.

[00:17:10] DPO: Four: retention. Three years for conversation records, as written. But the model
provider must not keep anything beyond what is needed to answer. If they keep prompts for thirty
days for abuse monitoring, I need to know that and I need to put it in the DPIA.

[00:18:00] DPO: And five: the patient identification. Date of birth plus a code to the mobile on
file is our standard, but on WhatsApp the number is already the identity. I would still want the
code before any booking action or any personal information is shown.

[00:19:30] IT: On staff identity, everything through Entra ID. And the assistant must act in
MediDesk as a technical user with its own rights, but every action must say on whose behalf.

[00:20:40] AL: Languages. German and English are mandatory. Turkish desirable. How many patients
write in Turkish?

[00:20:55] FD: In Munich, maybe one in ten messages on WhatsApp. In Vienna, more. Usually a family
member writes for the patient.

[00:21:20] DPO: Family members writing for patients is a problem for identification. The code goes
to the patient's phone, and the family member usually has it in hand, but formally we need the
patient's consent.

[00:22:00] SA: We will note that as an open question.

[00:23:15] COO: Something else. Reminders. Today we send an SMS 24 hours before with the time. No
preparation. I want the reminder to carry the preparation for that specific examination, and I want
the patient to be able to reply "I cannot come" and be rebooked.

[00:24:10] MD: The reminder at 72 hours matters most for colonoscopy, because the diet starts three
days before. For imaging with contrast, the question is kidney function and metformin.

[00:25:30] SA: Let us talk about the copilot. FD, what would help you most?

[00:25:45] FD: Honestly: when I open a message, I want to see in two lines what the patient wants,
their next appointments and whether we already answered them last week. And a draft reply that I
can send with one click when it is a simple one. But I want to send it. I do not want things going
out under my name that I did not see.

[00:26:40] COO: For the copilot that is fine, staff approve. For the patient assistant, I still
want automatic.

[00:27:10] MD: Automatic for booking and information. Never automatic for anything clinical.

[00:27:20] COO: Agreed.

[00:28:30] SA: Volume. Nine thousand written messages a week in the RFP. Do you expect the
assistant to change that?

[00:28:45] COO: If WhatsApp works, it will grow. We plan to open WhatsApp at all fourteen sites
next year. I would plan for double.

[00:30:00] IT: About the leaflets. Four hundred and twenty documents on SharePoint. Many are Word
with tables of medications and how many days to pause them. Some are scanned PDFs, old ones. The
owners update them, but not always the same file; sometimes they upload a new file and the old one
stays.

[00:30:50] MD: That is true. We do not have one place that says which leaflet is current.

[00:31:20] SA: That is important. If two versions exist, the assistant may quote the old one.

[00:31:30] MD: Then we have to fix that before go-live, not after.

[00:33:00] AL: Pilot. Which sites?

[00:33:10] COO: Munich and Vienna. Munich because it has the most WhatsApp traffic, Vienna because
of the languages. Three months of pilot, and then we decide.

[00:33:40] AL: What decides it?

[00:33:50] COO: Three numbers: first response time on written messages under one hour, same-day
cancellations for preparation reasons down by half, and no incident where the assistant gave a
wrong preparation instruction that harmed anyone.

[00:34:30] MD: And I want to read a sample of conversations every week during the pilot. My team,
not the vendor's.

[00:35:40] SA: Prices. The RFP says explain prices for self-payers. Where do they live?

[00:35:50] COO: In MediDesk, per examination and per site. They change quarterly. Do not let the
assistant invent a price. If it does not know, it says so.

[00:37:00] IT: Hosting. We are on Azure, Germany West Central. We would prefer the solution there,
but we are not religious about it as long as the DPO is happy.

[00:37:30] DPO: EU, a signed data processing agreement, no training, known retention. Those are my
four conditions.

[00:39:10] SA: Budget shape. We will cost it in the commercial annex. Is there anything that
constrains the running cost?

[00:39:25] COO: The running cost per month must be lower than two front-desk salaries. I will not
give you the number here.

[00:40:30] SA: Complaints. The RFP says ten percent are other: results, complaints. What should
the assistant do with a complaint?

[00:40:45] FD: Acknowledge it, never argue, hand it over. Complaints go to the site manager.

[00:41:30] MD: Results: never. "Your results are available in the patient portal" or "your doctor
will contact you". Nothing else.

[00:43:00] SA: One more on accessibility. Some of your patients are elderly.

[00:43:10] COO: The web chat must work with screen readers. And the language must be simple.

[00:45:20] IT: Monitoring. Who looks at it when it breaks on a Saturday?

[00:45:30] SA: That depends on the support hours you buy; we will propose options.

[00:45:40] IT: We need at least opening hours, including Saturday mornings.

[00:47:00] COO: Last thing from me. I have seen chatbots that say "I'm sorry, I can't help with
that" to everything. If it hands over half the conversations, it is useless. I want most simple
conversations finished without staff.

[00:47:25] SA: What is most, for you?

[00:47:30] COO: Seventy percent of booking and information conversations finished by the
assistant, by the end of the pilot.

[00:48:00] MD: Seventy percent finished, and of those finished, the preparation ones right. I do
not want seventy percent by giving wrong answers confidently.

[00:49:10] DPO: And please, in the design, show me exactly which data goes to the model and which
does not. A table.

[00:51:00] AL: We will send a summary and the open questions. Thank you all.

[00:51:10] COO: Thank you. We need the proposal in six weeks.

---

Open questions noted by the vendor during the call:

1. Consent when a family member writes for the patient.
2. Which leaflet is current when several versions exist.
3. Support hours on Saturdays.
4. Whether Turkish is in the pilot or later.
