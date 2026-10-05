# Acme Clinics — Request for Proposal

## AI patient assistant for booking, preparation and front-desk support

Issued by: Acme Clinics Group, Digital Office
Version: 1.2
Responses due: 6 weeks after issue

---

## 1. About Acme Clinics

Acme Clinics is a group of 14 outpatient clinics in Germany (11 sites) and Austria (3 sites):
diagnostic imaging, cardiology, gastroenterology, dermatology and general internal medicine. We
see about 310,000 patient visits a year. Patients reach us by phone, by the web booking form, by
e-mail and, since last year, by WhatsApp at four pilot sites.

Our front desks receive about 9,000 written patient messages a week across e-mail, the web
contact form and WhatsApp, and about 14,000 phone calls a week. Roughly 40% of written messages
concern booking, rescheduling or cancelling an appointment; 25% ask how to prepare for an
examination (fasting, medication, what to bring); 15% ask about prices, invoices and insurance;
the rest are results enquiries, complaints, and clinical questions.

## 2. The problem

- Front-desk staff spend most of their day answering the same written questions. Median first
  response to a written message is 19 working hours; at peak sites it is over two days.
- Missed preparation instructions cause about 6% of gastroenterology and imaging appointments to
  be cancelled on the day or repeated (the patient did not fast, did not pause a medication, or
  did not bring a referral).
- No-shows are 8% across the group. Patients who cannot reach us to reschedule simply do not come.
- Staff turnover at the front desk is high and new staff take months to know the preparation
  rules of every examination.

## 3. Scope

We are looking for a partner to design, build and operate an AI patient assistant with two faces.

### 3.1 Patient-facing assistant

Channels: the website chat, WhatsApp Business, and e-mail replies. Languages: German and English
are mandatory; Turkish is desirable.

The assistant shall:

1. Answer questions about opening hours, locations, accessibility, parking, and what to bring.
2. Answer preparation questions for every examination we offer, using our preparation leaflets.
3. Book, reschedule and cancel appointments in our practice management system (MediDesk) for
   examinations that do not require a doctor's triage first.
4. Send preparation reminders 72 hours and 24 hours before an appointment, with the instructions
   that apply to that examination.
5. Explain prices for self-paying patients and the cancellation fee policy.
6. Hand the conversation to a person when it cannot help, when the patient asks for one, or when
   the message is clinical.
7. Never give medical advice, diagnoses or interpretations of results.

### 3.2 Front-desk copilot

For staff, inside the front-desk web application:

1. Summarise each incoming written message and the patient's recent contact history.
2. Classify the message (booking, preparation, billing, results, complaint, clinical, other) and
   route it to the right queue.
3. Draft a reply for the staff member to edit and send.
4. Flag messages that suggest an urgent clinical situation so they are seen first.

## 4. Business rules that apply

- Cancellations later than 24 hours before the appointment incur a fee of EUR 30 for
  self-paying patients (EUR 50 for MRI and CT). Insured patients are not charged. The fee may be
  waived by a site manager.
- Refunds of any amount must be approved by the billing team.
- Some examinations (cardiac stress MRI, colonoscopy under sedation, contrast CT for patients over
  70) can only be booked after a doctor has reviewed the referral.
- A patient may hold at most two future appointments of the same examination type.
- Preparation leaflets are owned by the medical director of each specialty and are revised
  monthly; prices are revised quarterly.

## 5. Requirements for the solution

### 5.1 Quality

- The assistant must be 100% accurate on preparation instructions. A wrong instruction can harm a
  patient or waste an examination slot.
- Booking actions must never create a double booking or book an examination that requires a
  doctor's review.
- Clinical and urgent messages must be recognised and handed to a person.

### 5.2 Performance and availability

- Patient-facing replies within 5 seconds for chat and WhatsApp.
- Availability of 99.5% per month during clinic opening hours (Mon–Sat, 07:00–20:00 CET).
- The assistant must keep working (at least for information questions) when MediDesk is down.

### 5.3 Data protection and compliance

- The solution processes health data of patients in Germany and Austria and must comply with
  the GDPR, including Article 9, and with national rules on medical confidentiality.
- All patient data must be processed and stored in the EU. No patient data may be used to train
  any model.
- Conversation records must be kept for 3 years and then deleted; patients may request deletion
  earlier where the law allows.
- Every action the assistant takes in MediDesk must be auditable: who, what, when, on whose behalf.
- A data protection impact assessment (DPIA) will be required before go-live; the vendor must
  support it.

### 5.4 Integration

- MediDesk exposes a REST API for patients, appointments, slots and examination types. API rate
  limit: 20 requests per second per tenant.
- Identity: patients are identified by date of birth plus a one-time code sent to the mobile number
  on file. Staff use our Microsoft Entra ID.
- The preparation leaflets are currently PDF and Word files on a SharePoint site, about 420
  documents, 2 to 15 pages each, many with tables of medication pause times.

### 5.5 Operations

- The vendor operates the solution for 24 months after go-live, with monthly quality reports.
- We want to see, every month, how often the assistant was right, where it was wrong, and what was
  changed.

## 6. What we expect in the proposal

1. The technical design of the solution and why it is built that way.
2. How quality will be measured before and after go-live.
3. How patient data is protected.
4. The rollout approach (pilot sites first).
5. The operating model and costs (in a separate commercial annex).

## 7. Evaluation criteria

Technical design and its reasoning 35%, quality and safety approach 25%, data protection 20%,
experience 10%, commercial 10%.
