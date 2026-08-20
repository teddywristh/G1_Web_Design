# Legal AI Assistant

## Introduction

Legal AI Assistant is an intelligent web platform designed to make Vietnamese legal information easier to search, understand, analyze, and verify.

Vietnamese law is distributed across a large and constantly evolving collection of laws, codes, decrees, circulars, resolutions, decisions, consolidated documents, and other legal instruments. Finding the correct regulation often requires users to know where to search, which keywords to use, whether a document is still effective, whether it has been amended, and which specific Article or Clause applies to their situation.

For people without a legal background, this process can be difficult and time consuming.

Even when users successfully locate a relevant legal document, they may still need to read dozens or hundreds of pages before finding the provision that actually answers their question. Legal terminology, cross references between different regulations, amendments, and changes in legal effect can make this process even more complicated.

Legal AI Assistant is designed to simplify that experience.

Instead of requiring users to manually navigate through large collections of legal documents, the platform combines artificial intelligence, legal document search, structured legal data, and source based verification into one integrated system.

Users can describe a legal problem using natural language, search directly for legal documents, explore individual Articles and Clauses, ask questions about a specific document, and verify AI generated explanations against the original legal sources.

The platform is built around a simple idea:

**Legal information should not only be searchable. It should also be understandable and verifiable.**

The overall user journey is therefore designed around four actions:

**Ask → Search → Understand → Verify**

A user may begin with a question, discover the relevant regulations, understand how those regulations apply to the situation, and finally inspect the original legal provisions before making any decision.

---

# Project Purpose

The primary purpose of Legal AI Assistant is to reduce the complexity involved in accessing Vietnamese legal information.

Traditional legal research often requires users to perform several independent tasks.

They may need to search for a document, determine whether the document is still valid, identify amendments, find the correct Article or Clause, interpret legal terminology, compare multiple regulations, and determine how those regulations relate to a real world situation.

Legal AI Assistant brings these tasks into a unified web environment.

The project aims to create a platform where users can move naturally between legal search and artificial intelligence without losing access to the original legal sources.

The system is intended to help users answer questions such as:

> What regulations apply to my situation?

> Which Article or Clause contains this rule?

> Is this legal document still effective?

> Has this regulation been amended or replaced?

> What does this legal provision mean in simpler language?

> Which regulations should I read to understand this issue?

> What are the differences between these two legal provisions?

> Does this document contain provisions that may conflict with current regulations?

> Where did the AI obtain the legal basis for this answer?

Rather than returning only a generated answer, the platform is designed to guide users toward the legal evidence behind that answer.

---

# Project Objectives

Legal AI Assistant has several major objectives.

## 1. Make legal information easier to access

Users should not need to understand complex legal database structures before they can begin searching.

A person should be able to describe a situation in ordinary language and receive guidance toward relevant legal information.

For example:

```text
My employer has not paid my salary for two months.
What rights do I have?
```

Instead of expecting the user to know the correct law, decree, Article number, or legal terminology, the system analyzes the question and searches for potentially relevant regulations.

---

## 2. Make legal documents easier to understand

Finding a legal document does not necessarily mean understanding it.

Legal documents frequently contain specialized terminology, references to other regulations, exceptions, conditions, and complex sentence structures.

Legal AI Assistant uses artificial intelligence to explain these provisions in more accessible language while preserving references to the underlying legal sources.

The objective is not to remove legal detail.

The objective is to make the detail easier to understand.

---

## 3. Connect AI responses with legal evidence

One of the central design principles of the platform is traceability.

An AI answer should not exist separately from the legal documents that support it.

Whenever possible, an answer should identify:

1. The relevant legal document

2. The relevant Article

3. The relevant Clause

4. The legal explanation

5. The source that the user can inspect

This allows users to verify important information instead of treating an AI response as an unquestionable conclusion.

---

## 4. Reduce the time required for legal research

Legal research may involve searching through many documents before finding the correct regulation.

The platform attempts to reduce this workload by combining document retrieval, semantic search, artificial intelligence, document navigation, and legal citation into one workflow.

Instead of performing several separate searches, users can begin from a single legal question and progressively explore the relevant information.

---

## 5. Support users with different levels of legal knowledge

Legal AI Assistant is not designed exclusively for lawyers.

The platform should also be accessible to students, employees, business owners, researchers, organizations, and members of the public who need to understand Vietnamese law.

A user who does not know the name of a law should still be able to ask a question.

A user who already knows the document number should be able to search directly for that document.

A more experienced user should be able to inspect Articles, Clauses, document status, related regulations, and legal references.

The interface therefore supports both conversational exploration and traditional document based research.

---

# Who Can Use Legal AI Assistant?

The platform is designed for a broad range of users.

## General users

Individuals can use the platform to understand common legal questions related to employment, social insurance, housing, land, marriage, civil matters, transportation, administrative procedures, and other everyday legal situations.

For example:

```text
Can an employee terminate an employment contract immediately?

How is overtime salary calculated?

What documents are required to register a business?

What happens if a traffic fine is not paid?

Which regulations apply when buying an apartment?
```

---

## Students

Students can use the platform as a legal research assistant when studying regulations, analyzing legal cases, or identifying legal provisions relevant to an assignment.

Instead of searching only by keywords, students can explore relationships between legal questions and the documents that regulate them.

The citation system also encourages students to read the original legal provisions instead of relying entirely on generated explanations.

---

## Businesses

Businesses may use the platform to quickly investigate regulations related to taxation, employment, investment, commercial activities, contracts, intellectual property, accounting, insurance, and other areas relevant to business operations.

The platform can help identify which documents should be reviewed before a business makes a decision.

---

## Legal professionals

Legal professionals can use the platform as a research support tool.

The system can help locate potentially relevant provisions, summarize long documents, compare regulations, identify references, and reduce repetitive search work.

The final legal assessment, however, remains the responsibility of the professional using the information.

---

## Organizations and public institutions

Organizations that regularly create, review, or maintain internal regulations and legal documents may use the document review functionality to identify provisions that require further examination.

The system can assist with preliminary analysis before a human expert performs the final review.

---

# Main Features

# 1. AI Legal Assistant

The AI Legal Assistant is the primary conversational interface of the platform.

Users can ask questions about Vietnamese law using natural language instead of manually constructing complex legal search queries.

A user does not need to know the exact name of a law or the number of an Article before asking a question.

The system attempts to understand the legal intent behind the question, retrieve relevant legal information, and produce an explanation grounded in available legal documents.

---

## Natural Language Legal Questions

Users can describe a legal situation in the same way they would explain it to another person.

For example:

```text
I have worked for a company for three years and want to resign.
How much notice do I need to give?
```

or:

```text
My company wants employees to work on Sunday.
How should overtime salary be calculated?
```

or:

```text
What are the requirements for establishing a limited liability company in Vietnam?
```

The system analyzes the meaning of the question and attempts to determine which legal areas and regulations may be relevant.

---

## Legal Situation Analysis

Many legal questions cannot be answered correctly using only one keyword or one legal provision.

A user may provide information about:

1. Their role

2. Their employment situation

3. Contract conditions

4. Important dates

5. Financial values

6. Administrative circumstances

7. Business activities

8. Other relevant facts

The AI can use this context to provide a more structured explanation of the legal issue.

For example, rather than simply returning a law containing the word "termination", the system may distinguish between different forms of employment contract termination and explain which conditions are relevant to the situation described by the user.

---

## Legal Explanation

Legal documents are often written for precision rather than simplicity.

The AI Legal Assistant can translate complex legal language into a more readable explanation.

A response may contain several levels of information:

```text
Question
      ↓
Short Answer
      ↓
Legal Explanation
      ↓
Applicable Conditions
      ↓
Relevant Article and Clause
      ↓
Legal Source
      ↓
Verification
```

This structure allows users to obtain a quick understanding first and investigate the legal details afterward.

---

## Identification of Relevant Articles and Clauses

The system is designed to search beyond document titles.

When possible, the AI identifies the specific Article or Clause that contains the relevant legal rule.

Instead of receiving only:

```text
According to the Labor Code...
```

the user should receive more precise information such as:

```text
Relevant document

Labor Code

Relevant provision

Article X
Clause Y
```

The exact legal provision can then be opened and verified.

---

## Questions About Legal Effect

A legal document may have been amended, partially replaced, completely replaced, suspended, or rendered ineffective.

Therefore, simply finding a document is not sufficient.

Legal AI Assistant is designed to help users investigate questions related to legal effect, including:

1. Whether a document is currently effective

2. When the document became effective

3. Whether the document has been amended

4. Whether parts of the document have changed

5. Whether another document replaced it

6. Whether related implementation documents exist

This information is particularly important because an outdated legal provision may produce an incorrect interpretation of the current law.

---

## Questions Requiring Multiple Legal Documents

Some legal situations involve several layers of regulation.

For example, a question may involve a Law together with a Decree and a Circular.

The system can retrieve multiple relevant sources and organize them into a coherent explanation.

The intended reasoning process is:

```text
User Situation
      ↓
Identify Legal Topic
      ↓
Retrieve Relevant Documents
      ↓
Retrieve Relevant Articles
      ↓
Compare Applicable Rules
      ↓
Generate Explanation
      ↓
Provide Legal Sources
```

The purpose is to help users understand the relationship between regulations rather than presenting isolated search results.

---

## Questions Involving Calculations

Some legal questions contain numerical rules or formulas.

Examples may include:

1. Salary calculations

2. Overtime payment

3. Social insurance benefits

4. Contribution periods

5. Compensation

6. Financial thresholds

7. Administrative fees

For these situations, the system can combine retrieved legal rules with values provided by the user and present the calculation process.

A response should clearly distinguish between:

```text
Legal rule

User supplied information

Calculation

Result
```

This makes the result easier to inspect and reduces the risk that users misunderstand how a number was produced.

---

# 2. Legal Document Search

The Legal Document Search module allows users to perform traditional legal research directly within the website.

This feature is useful when users already know some information about the document they are looking for or want to explore a specific area of law.

The system provides both simple search and more detailed filtering capabilities.

---

## Keyword Search

Users can enter words or phrases related to the regulation they want to find.

For example:

```text
minimum wage

social insurance

personal income tax

land use certificate

employment contract

business registration
```

The search engine returns documents related to the query.

---

## Search by Document Title

If users know part or all of the document title, they can search specifically within document titles.

This is useful when the exact document number is unknown but the user remembers its subject.

---

## Search by Document Number

Users who know the document number can directly search for it.

For example:

```text
Document Number
      ↓
Search
      ↓
Matching Document
      ↓
Document Details
```

This provides a faster navigation path for experienced users.

---

## Search by Exact Phrase

For situations where a specific legal phrase is important, users can search for an exact expression rather than receiving results that contain only some of the keywords.

This can be useful when locating a known legal definition or provision.

---

# 3. Advanced Legal Document Filtering

Large legal databases may return many results for common terms.

Advanced filters allow users to narrow the search space.

Users can combine multiple filters to locate the most relevant documents.

---

## Filter by Document Type

Users can restrict results according to the legal instrument they are interested in.

Depending on the available dataset, examples can include:

1. Laws

2. Codes

3. Decrees

4. Circulars

5. Decisions

6. Resolutions

7. Consolidated documents

8. Official letters

9. Other regulatory documents

---

## Filter by Legal Field

Users can limit results to a specific area of law.

Possible legal fields include:

1. Taxation

2. Labor

3. Social Insurance and Health Insurance

4. Investment

5. Commerce

6. Enterprise

7. Accounting and Auditing

8. Intellectual Property

9. Land and Housing

10. Marriage and Family

11. Civil Law

12. Criminal Law

13. Environmental Protection

14. Construction

15. Banking and Finance

16. Securities

17. Education

18. Healthcare

19. Transportation

20. Administrative Law

The available fields depend on the legal database used by the platform.

---

## Filter by Issuing Authority

Users can search according to the government body or competent authority that issued the document.

This can help distinguish regulations issued by different authorities.

---

## Filter by Issuance Date

Users can define a period during which the document was issued.

For example:

```text
From: 01 January 2024

To: 31 December 2024
```

This is useful for researching regulations introduced during a particular period.

---

## Filter by Effective Date

Issuance date and effective date are not always the same.

The platform can allow users to search according to when a regulation became applicable.

This is particularly useful when determining which rules applied at a specific point in time.

---

## Filter by Legal Status

Users may restrict results according to whether a document is currently effective.

Possible statuses may include:

```text
Effective

Partially effective

Not yet effective

Expired

Replaced

Amended
```

Displaying legal status prominently helps users avoid relying on obsolete regulations.

---

## Filter by Year

Users can quickly restrict search results to documents issued within a selected year.

This provides a convenient option when researching recent legislative changes.

---

# 4. Legal Document Details

Search results lead users to a structured document page.

The purpose of this page is not only to display the full text but also to make the document easier to explore.

A document page may present:

```text
Document Title

Document Number

Document Type

Issuing Authority

Issuance Date

Effective Date

Legal Status

Legal Field

Document Content

Articles

Clauses

Related Sources
```

The document structure should allow users to navigate directly to individual Articles and Clauses instead of scrolling through the entire document.

This structure is especially useful for long legal documents.

---

# 5. Legal Citations and Source Verification

Legal citation is one of the most important features of Legal AI Assistant.

Artificial intelligence can produce fluent and convincing language even when information is incomplete or incorrect.

For legal information, users therefore need a way to inspect the evidence behind a response.

Legal AI Assistant is designed so that answers can be connected to their supporting legal sources.

A typical answer may follow this structure:

```text
AI Answer

        ↓

Legal Explanation

        ↓

Relevant Rule

        ↓

Article

        ↓

Clause

        ↓

Legal Document

        ↓

Original Source
```

---

## Citation Information

A citation may include:

1. Document name

2. Document number

3. Article number

4. Clause number

5. Relevant legal text

6. Legal status

7. Link to the complete document

When the user selects the citation, the platform can open the relevant legal document and navigate directly to the referenced provision.

---

## Why Citation Matters

Citation changes the role of the AI.

Without citations, users must trust the generated answer.

With citations, users can verify the answer.

The platform therefore follows the principle:

```text
Do not only provide an answer.

Provide the evidence required to verify the answer.
```

This is especially important for questions where regulations may have changed over time.

---

# 6. Ask AI About a Legal Document

Users do not always begin with a question.

Sometimes they already have the legal document they need but require help understanding it.

The Ask AI About a Document feature connects the document viewer directly to the AI assistant.

Instead of leaving the document page and starting another search, users can ask questions within the context of the document they are currently reading.

---

## Document Summary

Users can request a summary of a long document.

The AI may identify:

1. The main purpose of the document

2. The regulated subjects

3. Important requirements

4. Important rights and obligations

5. Major dates

6. Important Articles

7. Key changes introduced by the document

The summary provides an overview before the user reads the complete legal text.

---

## Explain a Legal Provision

Users can select an Article or Clause and ask the AI to explain it.

For example:

```text
Original Legal Provision
            ↓
       Ask AI
            ↓
Plain Language Explanation
            ↓
Conditions and Exceptions
            ↓
Related Provisions
```

This allows users to remain connected to the original legal text while receiving additional explanation.

---

## Find Relevant Provisions Within a Document

When a document is long, users may ask a question such as:

```text
Which Article explains the notice period for terminating this contract?
```

The system can search within the selected document and identify provisions that are most relevant to the question.

This removes the need to manually inspect every Article.

---

## Context Specific Questions

When users ask AI from a document page, the selected document becomes part of the question context.

For example:

```text
What obligations does this document impose on employers?
```

or:

```text
When does this regulation become effective?
```

or:

```text
Explain Article 15 in simpler language.
```

The system prioritizes information from the document currently being viewed.

---

# 7. AI Document Review

The AI Document Review module extends the platform beyond search and question answering.

It is intended to assist users who need to examine an existing document and compare its content against relevant legal regulations.

Possible documents include:

1. Draft legal documents

2. Internal company regulations

3. Policies

4. Administrative documents

5. Compliance documents

6. Other structured legal texts

The purpose is to identify provisions that may require additional human review.

---

## Upload a Document

Users can upload a document for analysis.

A DOCX file can be processed by the system and divided into structured units such as:

```text
Document

      ↓

Chapter

      ↓

Article

      ↓

Clause

      ↓

Paragraph
```

This allows the system to analyze individual provisions rather than treating the entire document as one block of text.

---

## Review Selected Provisions

Users may not need to review an entire document.

The system can allow users to submit one or several Articles or Clauses for analysis.

This can significantly reduce processing time when the user already knows which provisions require examination.

---

## Select the Comparison Scope

Different review tasks require different legal references.

The platform can allow users to determine which sources should be used during the review.

Possible options include:

1. Documents explicitly cited by the uploaded document

2. Specific legal documents selected by the user

3. Documents belonging to selected legal fields

4. The complete available legal database

This allows users to control the scope of the analysis.

---

## Article by Article Review

The system can review the uploaded document provision by provision.

Instead of returning only a single overall conclusion, the result can be organized according to individual Articles and Clauses.

For example:

```text
Article 1

No potential conflict identified


Article 2

Potential inconsistency detected

Relevant source:
Document A
Article X
Clause Y


Article 3

Additional review recommended
```

This makes the result easier to inspect and verify.

---

## Semantic Comparison

Two legal provisions may describe similar concepts using different words.

A search system based exclusively on keyword matching may fail to identify these relationships.

AI Document Review can use semantic analysis to compare meaning rather than relying only on identical vocabulary.

The conceptual process is:

```text
Provision from User Document
             ↓
       Meaning Analysis
             ↓
Relevant Legal Provisions
             ↓
     Semantic Comparison
             ↓
Potential Conflict or Overlap
```

This can help identify relationships that ordinary keyword search may miss.

---

## Conflict and Overlap Detection

The system can highlight content that may:

1. Conflict with another regulation

2. Duplicate an existing requirement

3. Use inconsistent terminology

4. Refer to an outdated legal basis

5. Introduce requirements that may require additional verification

6. Overlap with provisions in another document

The system should explain why a provision was flagged rather than providing only a warning.

---

## Analysis and Recommendations

When a potential issue is identified, the AI can provide an explanation containing:

```text
Provision Being Reviewed

Potential Issue

Relevant Legal Basis

Reason for the Flag

Related Article or Clause

Suggested Review Direction
```

Any recommendation should be treated as analytical assistance rather than an automatic legal decision.

---

## Side by Side Comparison

Users should be able to compare the analyzed provision with the source used as the legal basis.

A comparison interface may display:

```text
User Document                Legal Reference

Article 5                    Article 12

Original Content             Current Regulation

Selected Clause              Relevant Clause

            Comparison Analysis
```

This allows users to determine whether the AI interpretation is reasonable.

---

# 8. Legal Knowledge Base

The Legal Knowledge Base is the information foundation used by both the search engine and the AI assistant.

Legal documents should be stored as structured information rather than unorganized text files.

A document may contain metadata such as:

```text
Document ID

Document Name

Document Number

Document Type

Issuing Authority

Issuance Date

Effective Date

Legal Status

Legal Field

Articles

Clauses

References

Related Documents
```

---

## Article and Clause Level Indexing

Legal documents should be divided into smaller legal units.

Instead of indexing only an entire document, the system can index:

```text
Document
   ↓
Article
   ↓
Clause
   ↓
Legal Content
```

This allows the search engine and AI to retrieve the exact portion of a document that is relevant to a question.

For example, if only Clause 2 of Article 15 is relevant, the system should not need to send the entire document to the AI.

This improves search precision and makes citations more useful.

---

# 9. How Legal AI Assistant Works

From a user's perspective, the system should feel simple.

The internal process, however, involves several stages.

```text
                  User
                    │
                    ▼
           Natural Language Question
                    │
                    ▼
              Query Analysis
                    │
                    ▼
          Legal Intent Detection
                    │
                    ▼
          Legal Knowledge Search
                    │
                    ▼
      Relevant Documents and Provisions
                    │
                    ▼
             Context Selection
                    │
                    ▼
           AI Legal Reasoning
                    │
                    ▼
             Answer Generation
                    │
                    ▼
        Legal Citation Attachment
                    │
                    ▼
         User Receives Response
                    │
                    ▼
          Source Verification
```

The important principle is that legal retrieval occurs before the final answer is produced.

The intended workflow is therefore not:

```text
Question
   ↓
AI guesses an answer
```

Instead, it is:

```text
Question
   ↓
Understand the legal problem
   ↓
Search the legal knowledge base
   ↓
Retrieve relevant legal provisions
   ↓
Use those provisions as context
   ↓
Generate an explanation
   ↓
Attach citations
   ↓
Allow the user to verify the source
```

---

# 10. Typical User Journey

Consider a user who wants to know whether they can terminate an employment contract.

The user begins by typing:

```text
I have an indefinite employment contract.
Can I resign without providing a reason?
```

The platform analyzes the question and identifies employment law as the relevant legal area.

It searches the legal database for provisions related to:

```text
Employment contract

Employee termination rights

Notice period

Exceptions to notice requirements
```

Relevant Articles and Clauses are retrieved.

The AI then produces an explanation using these provisions.

The response may contain:

```text
Short Answer

Explanation

Applicable Conditions

Required Notice Period

Possible Exceptions

Relevant Legal Documents

Article and Clause References
```

The user can select a citation.

The corresponding legal document opens.

The page navigates to the relevant Article or Clause.

The user can now read the original legal provision and determine whether the AI explanation correctly represents the source.

The full workflow becomes:

```text
Ask
 ↓
Receive Explanation
 ↓
Inspect Citation
 ↓
Open Legal Document
 ↓
Read Article
 ↓
Verify Information
```

This interaction represents the core philosophy of Legal AI Assistant.

---

# 11. Search First User Journey

Some users prefer traditional search.

For example, a user may already know the document number.

The workflow becomes:

```text
Enter Document Number
        ↓
Search
        ↓
Open Document
        ↓
Navigate Articles
        ↓
Select Provision
        ↓
Ask AI
        ↓
Receive Explanation
```

Search and AI therefore complement each other.

The search engine helps users discover authoritative information.

The AI helps users understand that information.

---

# 12. AI First User Journey

Users who do not know which law applies can begin directly with AI.

```text
Describe Legal Situation
        ↓
AI Identifies Legal Topic
        ↓
Relevant Regulations Retrieved
        ↓
Answer Generated
        ↓
Sources Displayed
        ↓
User Opens Original Documents
```

This workflow is particularly useful for people without formal legal knowledge.

They do not need to translate their real world problem into legal terminology before searching.

---

# 13. Document First User Journey

Users may also begin from a document.

```text
Open Legal Document
        ↓
Read Document
        ↓
Select Article
        ↓
Ask AI to Explain
        ↓
Explore Related Provisions
        ↓
Continue Research
```

This turns the document viewer into an interactive legal research environment rather than a static text page.

---

# 14. User Experience Principles

Legal AI Assistant is designed around several important user experience principles.

## Simple First Interaction

A new user should be able to begin by typing a legal question.

The system should not require the user to understand legal database structures before using the platform.

---

## Progressive Detail

Responses should begin with understandable information and allow the user to explore more detail when necessary.

For example:

```text
Simple Explanation
        ↓
Detailed Analysis
        ↓
Article and Clause
        ↓
Full Legal Document
```

This approach serves both beginners and experienced users.

---

## Source Transparency

Users should always understand where important legal information came from.

Legal citations should therefore be visible and easy to open.

---

## Clear Legal Status

When displaying a legal document, the platform should clearly communicate its current legal status.

Users should not need to search elsewhere merely to determine whether a document is still effective.

---

## Human Verification

The interface should encourage users to inspect legal evidence when decisions have significant consequences.

AI is a research assistant, not an authority that replaces the legal source.

---

# 15. Reliability and Responsible AI

Legal information can directly affect employment, finances, property, business operations, administrative procedures, and other important decisions.

For this reason, Legal AI Assistant is designed around a source based approach.

The AI should primarily reason using legal information retrieved from the platform's legal knowledge base.

Whenever possible, important legal claims should be accompanied by references that users can inspect.

However, artificial intelligence remains imperfect.

Potential limitations include:

1. Incorrect interpretation of a legal provision

2. Missing context from the user's situation

3. Retrieval of an incomplete set of relevant regulations

4. Ambiguous legal language

5. Recently changed regulations that have not yet been processed

6. Complex legal situations that require professional judgment

7. Differences between general legal rules and specific factual circumstances

Users should therefore treat AI generated responses as assistance for legal research and understanding, not as automatically authoritative conclusions.

---

# 16. What Legal AI Assistant Is

Legal AI Assistant is intended to be:

```text
A Legal Information Platform

A Legal Search Tool

An AI Research Assistant

A Legal Document Explorer

A Source Discovery System

A Legal Explanation Tool

A Document Review Assistant
```

It helps users discover information and understand legal sources more efficiently.

---

# 17. What Legal AI Assistant Is Not

Legal AI Assistant is not:

```text
A Court

A Government Authority

A Law Firm

A Licensed Lawyer

An Automatic Legal Decision Maker

A Replacement for Professional Legal Advice
```

The platform provides information and analytical assistance.

It does not make legally binding decisions.

---

# 18. Core Platform Concept

Legal AI Assistant combines three major capabilities:

```text
Legal Search
      +
Legal Knowledge Base
      +
Artificial Intelligence
```

Each component solves a different problem.

**Legal Search** helps users locate information.

**The Legal Knowledge Base** provides structured and traceable legal sources.

**Artificial Intelligence** helps users understand and interact with those sources using natural language.

Together, they create a complete legal information workflow.

```text
Search
   ↓
Discover

AI
   ↓
Understand

Citation
   ↓
Verify
```

---

# 19. Vision

The long term vision of Legal AI Assistant is to create a legal information environment where users do not need to choose between a traditional search engine and an AI assistant.

Both should operate as parts of the same system.

A user should be able to move freely between:

```text
Question

Search Result

Legal Document

Article

Clause

AI Explanation

Related Regulation

Source Verification
```

Every interaction should help the user move closer to the original legal information rather than further away from it.

The platform therefore aims to transform legal research from a fragmented process into an integrated experience.

Instead of:

```text
Search Google
      ↓
Open Multiple Websites
      ↓
Read Several Documents
      ↓
Find Relevant Article
      ↓
Check Legal Status
      ↓
Interpret Legal Language
      ↓
Compare Regulations
```

Legal AI Assistant aims to provide:

```text
Ask or Search
      ↓
Find Relevant Law
      ↓
Understand the Rule
      ↓
Inspect the Legal Basis
      ↓
Verify the Source
```

The ultimate goal is to make Vietnamese legal information more accessible while preserving the transparency and source verification required for responsible legal research.

---

# Disclaimer

Legal AI Assistant is an information retrieval, legal research, and decision support platform.

The platform uses artificial intelligence to help users discover, summarize, explain, compare, and understand legal information.

AI generated responses may contain errors, omit relevant information, misunderstand the facts provided by the user, or fail to reflect the most appropriate interpretation of a regulation.

Information generated by the platform should therefore not be considered legal advice, an official legal interpretation, or a substitute for advice from a qualified legal professional.

For important legal, financial, administrative, contractual, or business decisions, users should verify the information against the original legal documents and consult an appropriate legal professional or competent authority when necessary.

The final responsibility for interpreting and applying legal information remains with the user and the relevant qualified professionals or authorities.
