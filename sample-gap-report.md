# KnowledgeLoop sample gap report

**Dataset:** included demo tickets and knowledge articles  
**Generated:** 19 November 2026  
**Scope:** 9 resolved tickets · 2 existing articles · 3 issue clusters

## Summary

| Finding | Count |
| --- | ---: |
| Recurring clusters without an article | 1 |
| Existing articles flagged for review | 2 |
| Covered clusters with no freshness flag | 0 |

## Content gap: Authenticator code rejected after phone migration

**Volume:** 3 tickets — SUP-4821, SUP-4836, SUP-4899  
**Finding:** No matching knowledge article. Draft is pending expert review.

### Draft article

#### Symptoms

- Authenticator codes are rejected after moving to a new phone.
- The new phone's one-time passcodes fail during sign-in.
- Sign-in says the verification code is invalid after the employee changed phones.

#### Cause

The ticket notes consistently identify an old authenticator enrollment or credential still attached to the account after the phone was replaced.

#### Steps

1. Open **Admin → Users**, select the affected user, and open **Security**.
2. Remove the authenticator credential or device enrollment associated with the retired phone.
3. Enroll the authenticator app again on the replacement phone, using the new QR code if prompted.
4. Save the new recovery codes.

#### Verification

Ask the user to sign in with a newly generated code from the replacement phone. Confirm that the code is accepted and that recovery codes are available.

**Evidence:** SUP-4821, SUP-4836, SUP-4899. The draft sections above are assembled from the supplied resolution fields; an expert should confirm the exact current UI path before approval.

## Stale article: Export a report to CSV

**Article:** KB-1182 · written for version 6.2 · last reviewed 18 February 2025  
**Recent tickets:** SUP-4770, SUP-4802, SUP-4854 on version 6.8

The article says the export includes all filtered rows by default and describes the classic dialog. Recent fixes set **Export scope** to **All filtered rows** instead of **Current page**. The article's instructions are contradicted by current resolution notes and apply to an older product version.

**Recommended review:** Update screenshots and instructions for the v6.8 export dialog; verify its default scope with a product expert.

## Stale article: Fix SSO sign-in loops after certificate updates

**Article:** KB-1042 · written for version 6.4 · last reviewed 14 January 2025  
**Recent tickets:** SUP-4791, SUP-4868, SUP-4883 on version 6.8

The article points to **Security → SAML Connections**. Recent fixes use **Admin → Identity → SSO**, replace the current signing certificate, confirm the entity ID, and invalidate sessions. The ticket evidence indicates the article's UI path is outdated for the current version.

**Recommended review:** Confirm the v6.8 settings path and session-clearing step, then revise and re-verify the article.

## Review and indexing

KnowledgeLoop holds the MFA draft in its review queue. An expert can edit the title, symptoms, cause, steps, and verification, then approve it. The app indexes only after approval; stale-article flags are recommendations for a knowledge owner to verify.
