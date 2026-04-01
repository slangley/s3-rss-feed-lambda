s3-rss-feed-lambda/
  ├── serverless.yml      # Full AWS infra (Lambda, S3, CloudFront, ACM, Route53)
  ├── handler.py          # Python Lambda — lists bucket, generates RSS, invalidates cache
  ├── .env.example        # Template — copy to .env and fill in your values
  └── .gitignore          # Excludes .env, .serverless/, __pycache__

  Next steps

  1. Copy and fill in your config:
  cp .env.example .env
  # Edit .env with your actual domain, name, email, etc.
  2. Install Serverless Framework:
  npm install -g serverless
  3. Deploy (first deploy takes 10-20 min — CloudFront global rollout):
  serverless deploy --stage prod
  4. Upload a test MP3 named like 2026-03-31-my-first-episode.mp3 and check Lambda logs:
  aws s3 cp ./2026-03-31-my-first-episode.mp3 s3://podcast-rss-feed-prod-audio/
  serverless logs --function generateRss --stage prod --tail
  curl https://podcast.yourdomain.com/rss.xml

  One thing to note

  The existing: true on the S3 event trigger means Serverless Framework creates the bucket in Resources first, then
  wires up the Lambda notification separately. If you see a CircularDependency error on first deploy, let me know —
  there's a straightforward fix using NotificationConfiguration directly on the bucket resource.