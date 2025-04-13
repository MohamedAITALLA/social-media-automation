# YouTube Channel Monitor

A web application for monitoring YouTube channels and sending notifications about new videos.

## Features

- Monitor multiple YouTube channels
- Receive notifications when new videos are published
- Set up webhooks for integration with other systems
- Dashboard with channel and video statistics

## Deployment to Vercel

### Prerequisites

1. A [Vercel](https://vercel.com/) account
2. [Node.js](https://nodejs.org/) installed locally
3. [Vercel CLI](https://vercel.com/docs/cli) installed (`npm i -g vercel`)
4. A [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) database
5. [YouTube Data API](https://developers.google.com/youtube/v3/getting-started) key

### Environment Variables

The following environment variables need to be configured in your Vercel project:

```
SECRET_KEY=your_secret_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/youtube-monitor?retryWrites=true&w=majority
POLLING_INTERVAL=3600
MAX_RETRIES=3
RETRY_DELAY=300
LOG_LEVEL=INFO
SOCKETIO_ASYNC_MODE=threading
SESSION_COOKIE_SECURE=False
VERCEL=true
```

You can set these in the Vercel dashboard under Project Settings > Environment Variables.

### Deployment Steps

1. Clone this repository
   ```bash
   git clone https://github.com/yourusername/youtube-monitor.git
   cd youtube-monitor
   ```

2. Login to Vercel
   ```bash
   vercel login
   ```

3. Deploy to Vercel
   ```bash
   vercel
   ```

4. Follow the prompts to configure your project
   - When asked for your output directory, press Enter to use the default
   - When asked about Environment Variables, you can set them now or later in the Vercel dashboard

5. (Optional) To deploy to production
   ```bash
   vercel --prod
   ```

### Limitations in Vercel Deployment

Since Vercel uses a serverless architecture, there are some limitations:

1. **Background tasks**: The monitoring task won't run continuously as it would on a traditional server. Consider setting up a separate service or using Vercel Cron Jobs for scheduled tasks.

2. **WebSockets**: Real-time functionality via Socket.IO will have limited capabilities in the serverless environment.

3. **Statelessness**: Each function invocation is stateless, so don't rely on in-memory storage between requests.

## Local Development

1. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on `.env.example` and set your environment variables

4. Run the application
   ```bash
   python run.py
   ```

5. Access the application at `http://localhost:5000`

## License

MIT
