# Security Policy

## ⚠️ Important Security Notice

This is an **open-source reference implementation** of a dropshipping automation system.

**DO NOT USE IN PRODUCTION WITHOUT PROPER SECURITY REVIEW**

---

## 🔒 Security Considerations

### **API Credentials**

- ❌ **NEVER** commit `.env` files with real API keys
- ❌ **NEVER** commit database files with real data
- ❌ **NEVER** hardcode credentials in source code
- ✅ **ALWAYS** use `.env.example` as template only
- ✅ **ALWAYS** add sensitive files to `.gitignore`
- ✅ **ALWAYS** regenerate tokens if accidentally exposed

### **Database Security**

- 🔒 Database files (`.db`, `.sqlite`) are **gitignored**
- 🔒 Contains real product data, customer information
- 🔒 Must be backed up securely (encrypted)
- 🔒 Never share production databases publicly

### **Token Management**

- 🔄 eBay tokens expire regularly (use auto-refresh)
- 🔄 AliExpress tokens expire (use auto-refresh)
- 🔐 Store tokens encrypted at rest
- 🔐 Use environment variables, not config files

---

## 🚨 Reporting a Vulnerability

**This is a read-only educational project.**

If you discover a security vulnerability in the code:

1. **DO NOT** open a public issue
2. **DO NOT** share exploit details publicly
3. Review the code yourself and apply fixes in your fork
4. This project does not have active maintainers for security patches

---

## ⚙️ Best Practices for Users

If you deploy this system:

1. ✅ **Audit the code** before use
2. ✅ **Review all API calls** for security
3. ✅ **Use separate test accounts** first
4. ✅ **Enable 2FA** on eBay/AliExpress accounts
5. ✅ **Monitor API usage** for anomalies
6. ✅ **Keep dependencies updated** (`pip install -U`)
7. ✅ **Use HTTPS** for all API communication
8. ✅ **Implement rate limiting** to avoid bans
9. ✅ **Log all operations** for audit trail
10. ✅ **Backup regularly** (code + database)

---

## 🛡️ What This Project Does NOT Include

- ❌ No payment processing (you handle manually)
- ❌ No customer payment data storage
- ❌ No credit card handling
- ❌ No PII (personally identifiable information) beyond order emails

---

## 📜 Compliance

Users must ensure compliance with:

- ✅ eBay Terms of Service
- ✅ AliExpress Terms of Service
- ✅ GDPR (if handling EU customer data)
- ✅ Local e-commerce regulations
- ✅ Tax laws in your jurisdiction

**This project does not provide legal advice.**

---

## 🔍 Known Limitations

- ⚠️ Relies on third-party APIs (eBay, AliExpress)
- ⚠️ API rate limits apply
- ⚠️ No built-in encryption for `.env` files
- ⚠️ Logs may contain sensitive data (review before sharing)
- ⚠️ Auto-purchase feature requires careful monitoring

---

## 🆘 Disclaimer

**USE AT YOUR OWN RISK**

This software is provided "AS IS" without warranty of any kind.
The authors are NOT responsible for:

- Financial losses
- Account suspensions
- Security breaches
- Legal issues
- Data loss

---

**Mondeora Team**  
*Security is your responsibility when using this code*
