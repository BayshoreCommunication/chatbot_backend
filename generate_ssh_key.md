# SSH Key Generation Guide

## On your local machine:

```bash
# Generate SSH key pair
ssh-keygen -t rsa -b 4096 -C "github-actions-deploy"

# When prompted:
# - File location: Press Enter (default: ~/.ssh/id_rsa)
# - Passphrase: Press Enter (leave empty for automation)

# Copy the PUBLIC key to your DigitalOcean server
ssh-copy-id root@YOUR_DROPLET_IP

# Or manually copy the public key content:
cat ~/.ssh/id_rsa.pub
```

## Add to DigitalOcean server:

```bash
# SSH into your droplet
ssh root@YOUR_DROPLET_IP

# Create .ssh directory if it doesn't exist
mkdir -p ~/.ssh

# Add your public key to authorized_keys
echo "your-public-key-content" >> ~/.ssh/authorized_keys

# Set proper permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

## Add to GitHub Secrets:

1. Copy the PRIVATE key content:

```bash
cat ~/.ssh/id_rsa
```

2. Add to GitHub repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Add new secret: `SSH_KEY`
   - Paste the ENTIRE private key including:
     - `-----BEGIN OPENSSH PRIVATE KEY-----`
     - All the key content
     - `-----END OPENSSH PRIVATE KEY-----`
