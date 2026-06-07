# Email Deliverability & BIMI Implementation Roadmap

## Current Status (MxToolbox Report)

**Passing:**
- ✅ SPF record valid
- ✅ MX records configured with redundancy
- ✅ No blacklist issues

**Warnings:**
- ⚠️ BIMI: no record found
- ⚠️ DMARC: rua not set to MxToolbox
- ⚠️ Inbox placement not tested

---

## 1. DMARC Reporting Configuration (High Priority)

### Current DMARC Record
Check current DMARC configuration:
```bash
dig +short TXT _dmarc.ricohunt.com
```

### Action: Add MxToolbox Reporting
Add MxToolbox as a DMARC report recipient to monitor authentication failures.

**Format:**
```
rua=mailto:dmarc-agg@mxtoolbox.com
```

**Updated DMARC Record Example:**
```
v=DMARC1; p=reject; pct=100; rua=mailto:dmarc-agg@mxtoolbox.com,mailto:your-email@ricohunt.com; adkim=r; aspf=r
```

**Steps:**
1. Log into DNS provider (Vercel/Cloudflare/other)
2. Edit `_dmarc.ricohunt.com` TXT record
3. Add `rua=mailto:dmarc-agg@mxtoolbox.com` to existing rua tags
4. Save and wait 24-48 hours for propagation
5. Verify with MxToolbox DMARC lookup

**Note:** Keep existing rua tags if present to maintain current reporting.

---

## 2. BIMI Implementation (Medium Priority)

### Prerequisites Checklist

#### A. DMARC Enforcement
- Current DMARC must be `p=quarantine` or `p=reject` (not `p=none`)
- `pct=100` (or absent, defaults to 100)
- SPF and DKIM must be properly configured

**Migration Path (if currently p=none):**
1. `p=none` → `p=quarantine` (monitor 2-8 weeks)
2. `p=quarantine` → `p=reject` (after verification)

#### B. SVG Tiny-PS Logo Compliance

**Current Logo Status:**
- ✅ Square (1024x1024)
- ✅ No scripts
- ✅ No external fonts
- ✅ No raster images
- ⚠️ May not be SVG Tiny-PS compliant (needs `version="1.2"` and `baseProfile="tiny-ps"`)

**SVG Tiny-PS Requirements:**
- `version="1.2"` attribute in root `<svg>` element
- `baseProfile="tiny-ps"` attribute in root `<svg>` element
- Square viewBox (e.g., `viewBox="0 0 1024 1024"`)
- File size under 32 KB
- No JavaScript (`<script>`)
- No CSS (`<style>`, `style=`)
- No external images (`<image>` with URL)
- No animations (`<animate>`, `<animateTransform>`)
- No hyperlinks (`<a>`)
- Required `<title>` element

**Current logo at `/bimi/rico-bimi.svg` is simplified but may need conversion.**

**Conversion Tool:**
- CaptainDNS BIMI SVG converter: https://www.captaindns.com/en/tools/images/bimi-svg-converter

#### C. Certificate Choice: VMC vs CMC

**VMC (Verified Mark Certificate):**
- **Requirement:** Registered trademark (figurative, not word mark)
- **Recognized offices:** USPTO, EUIPO, INPI, UKIPO, CIPO, IP Australia, DPMA, OEPM, UIBM
- **Timeline:** 4-12 months (including trademark filing if not already registered)
- **Cost:** $250-350 (USPTO filing) + certificate fee (~$1,000-2,000)
- **Support:** Gmail, Apple Mail, Yahoo Mail
- **Badge:** Blue checkmark in Gmail

**CMC (Common Mark Certificate):**
- **Requirement:** 12 months of documented public logo usage
- **Evidence:** Web archive screenshots, invoices, social media posts, marketing materials
- **Timeline:** 1-4 weeks
- **Cost:** ~$500-1,000
- **Support:** Gmail, Yahoo Mail (NOT Apple Mail)
- **Badge:** No blue checkmark

**Recommendation for Rico:**
- If Rico logo has been used publicly for 12+ months → CMC (faster, cheaper)
- If Rico has registered trademark → VMC (full support, blue checkmark)
- If neither → Wait for 12 months usage proof or file trademark

### BIMI DNS Record Format

**Record Name:** `default._bimi.ricohunt.com`  
**Record Type:** TXT  
**TTL:** 3600

**With Certificate (VMC/CMC):**
```
v=BIMI1; l=https://ricohunt.com/bimi/rico-bimi.svg; a=https://ricohunt.com/bimi/rico-cert.pem
```

**Without Certificate (Self-Declared, Yahoo Only):**
```
v=BIMI1; l=https://ricohunt.com/bimi/rico-bimi.svg; a=;
```

**Important:**
- Use `default._bimi.domain.com`, NOT `_bimi.domain.com`
- Both URLs must use HTTPS
- PEM certificate must include full chain
- No stray characters or extra spaces

### Verification Steps

**1. Check BIMI DNS Record:**
```bash
dig +short TXT default._bimi.ricohunt.com
```

**2. Check SVG Accessibility:**
```bash
curl -I https://ricohunt.com/bimi/rico-bimi.svg
```
Expected: HTTP 200, Content-Type: image/svg+xml

**3. Check PEM Certificate Accessibility:**
```bash
curl -I https://ricohunt.com/bimi/rico-cert.pem
```
Expected: HTTP 200

**4. Check DMARC Record:**
```bash
dig +short TXT _dmarc.ricohunt.com
```
Expected: p=quarantine or p=reject, pct=100

**5. Use Verification Tool:**
- CaptainDNS BIMI Record Check
- MxToolbox BIMI Lookup

### Testing Display

**Gmail:**
- Send test email to Gmail account
- Logo appears next to sender name
- Blue checkmark if VMC
- Caching: few hours to few days

**Apple Mail:**
- Check iOS and macOS
- VMC only (CMC not supported)
- iCloud server must verify certificate

**Yahoo Mail:**
- Most permissive
- Displays logo even without certificate (self-declared)
- Good for initial DNS testing

**Timeline:** 1-72 hours for full propagation

---

## 3. Inbox Placement Testing (Medium Priority)

### Recommended Tools

**MailReach:**
- URL: https://www.mailreach.co
- Focus: B2B-weighted seed list (Gmail Workspace, Outlook 365)
- Features: Automated warmup, reputation protection
- Best for: Cold email campaigns

**MailGenius:**
- URL: https://www.mailgenius.com/inbox-placement-test/
- Features: Free test, no sign-up required
- Best for: Quick one-off checks

**EasyDMARC:**
- URL: https://easydmarc.com/tools/email-deliverability-test
- Features: Gmail, Outlook, Yahoo placement
- Best for: Comprehensive deliverability suite

**Instantly.ai:**
- URL: https://instantly.ai/inbox-placement
- Features: Unlimited automated tests
- Best for: High-volume senders

### Testing Process

1. **Configure sending setup** - Use realistic sending infrastructure
2. **Choose seed list** - Representative inboxes (Gmail, Outlook, Yahoo)
3. **Send test campaign** - Live email to seed addresses
4. **Review placement** - Check inbox vs spam folder
5. **Analyze issues** - Content, authentication, reputation
6. **Iterate** - Fix issues and retest

---

## Implementation Priority Order

1. **Immediate (Today):**
   - Add MxToolbox rua to DMARC record
   - Verify DMARC enforcement (p=quarantine or p=reject)

2. **Short-term (1-2 weeks):**
   - Convert logo to SVG Tiny-PS format
   - Run inbox placement test
   - Decide VMC vs CMC path

3. **Medium-term (1-3 months):**
   - Obtain certificate (VMC or CMC)
   - Host PEM certificate
   - Publish BIMI DNS record

4. **Long-term (3-12 months):**
   - File trademark if pursuing VMC
   - Monitor DMARC reports
   - Regular inbox placement testing

---

## Cost Estimates

**DMARC Reporting:** Free (MxToolbox)

**BIMI Logo Conversion:** Free (CaptainDNS tool)

**CMC Certificate:** ~$500-1,000

**VMC Certificate:** ~$1,000-2,000 + trademark filing ($250-350 USPTO)

**Inbox Placement Testing:**
- MailGenius: Free (one-off)
- MailReach: ~$50-100/month
- EasyDMARC: ~$50-200/month

---

## References

- MxToolbox DMARC RUA: https://mxtoolbox.com/dmarc/details/dmarc-tags/dmarc-rua
- CaptainDNS BIMI Guide: https://www.captaindns.com/en/blog/bimi-vmc-cmc-certificate-guide
- MxToolbox BIMI Setup: https://mxtoolbox.com/dmarc/bimi/how-to-create-bimi-record
- MailReach Inbox Testing: https://www.mailreach.co/blog/inbox-placement-testing
- BIMI Group: https://bimigroup.org
