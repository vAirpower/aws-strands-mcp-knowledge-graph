# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in the AWS Strands MCP Knowledge Graph project, please report it responsibly:

### 🔒 Private Disclosure Process

1. **Email**: Send details to [security@vairpower.com](mailto:security@vairpower.com)
2. **Subject Line**: Use "SECURITY: AWS Strands MCP Knowledge Graph - [Brief Description]"
3. **Encryption**: Use PGP encryption when possible for sensitive information
4. **Response Time**: We will acknowledge receipt within 48 hours

### 📋 What to Include

Please provide the following information:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested remediation (if available)
- Your contact information

### ⏱️ Responsible Disclosure Timeline

- **Day 0**: Vulnerability reported
- **Day 2**: Confirmation of receipt and initial assessment
- **Day 7**: Detailed analysis and impact assessment complete
- **Day 14**: Fix development begins
- **Day 30**: Security patch released (target)
- **Day 90**: Public disclosure (after fix deployment)

## 🛡️ Security Best Practices

### For Users

- **Never commit credentials**: Always use environment variables or AWS credential files
- **Keep dependencies updated**: Regularly run `pip install --upgrade -r requirements.txt`
- **Monitor AWS usage**: Review your AWS CloudTrail logs and billing
- **Use IAM roles**: Prefer IAM roles over access keys when possible
- **Enable MFA**: Use multi-factor authentication on your AWS account

### For Contributors

- **Code scanning**: Run security scanners before submitting PRs
- **Dependency analysis**: Check for known vulnerabilities in dependencies
- **Input validation**: Validate all user inputs and API responses
- **Secure defaults**: Use secure configurations by default
- **Least privilege**: Request minimal required permissions

## 🔍 Security Features

### Current Security Measures

- **Environment-based configuration**: No hardcoded credentials
- **Input validation**: SPARQL query sanitization
- **Network security**: Local development server binding
- **Dependency scanning**: Automated vulnerability checks
- **Error handling**: Secure error messages without sensitive data exposure

### AWS Security Integration

- **IAM Integration**: Uses AWS IAM for authentication and authorization
- **Bedrock Security**: Leverages AWS Bedrock's built-in security features
- **VPC Support**: Can be deployed within AWS VPC for network isolation
- **CloudTrail Logging**: All AWS API calls are logged for audit

## 📊 Supported Versions

| Version | Security Support |
|---------|------------------|
| 1.0.x   | ✅ Active        |
| < 1.0   | ❌ End of Life   |

## 🚨 Known Security Considerations

### Current Limitations

1. **Local Development**: Default configuration runs on localhost without authentication
2. **In-Memory Data**: RDF data is stored in memory without persistence encryption
3. **HTTP Communication**: MCP server uses HTTP by default (not HTTPS)
4. **Resource Limits**: No built-in rate limiting for SPARQL queries

### Recommended Production Hardening

1. **Enable HTTPS**: Configure TLS certificates for production deployment
2. **Add Authentication**: Implement authentication for the MCP server
3. **Rate Limiting**: Add request rate limiting to prevent abuse
4. **Network Security**: Deploy behind a firewall or within a VPC
5. **Monitoring**: Implement comprehensive logging and monitoring

## 🔐 AWS Security Requirements

### Required IAM Permissions

Minimum required permissions for AWS Bedrock access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-7-sonnet-*"
      ]
    }
  ]
}
```

### AWS Account Security

- Enable AWS CloudTrail for API call logging
- Use AWS Config for compliance monitoring
- Configure AWS GuardDuty for threat detection
- Implement AWS IAM Access Analyzer for permission reviews

## 🛠️ Security Testing

### Automated Security Checks

The project includes automated security scanning:

```bash
# Dependency vulnerability scanning
pip install safety
safety check

# Static code analysis
pip install bandit
bandit -r . -f json

# Type checking for security
mypy . --strict
```

### Manual Security Testing

Before deploying to production:

1. **Credential scanning**: Verify no credentials in code
2. **Input validation testing**: Test with malicious SPARQL queries
3. **Network security**: Verify proper network configuration
4. **AWS permission testing**: Confirm least-privilege access

## 📞 Security Contacts

- **Primary**: [security@vairpower.com](mailto:security@vairpower.com)
- **Backup**: [admin@vairpower.com](mailto:admin@vairpower.com)
- **GitHub**: [@vAirpower](https://github.com/vAirpower)

## 🙏 Acknowledgments

We appreciate security researchers who:
- Follow responsible disclosure practices
- Provide detailed vulnerability reports
- Work with us to improve security
- Allow time for fixes before public disclosure

---

**Remember**: Security is everyone's responsibility. When in doubt, ask questions and err on the side of caution.
