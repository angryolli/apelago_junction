# Ocean Opportunity Radar

Ocean Opportunity Radar turns fragmented startup data into actionable investment intelligence for the blue economy. It helps investors, accelerators, and ecosystem organizations discover promising ocean startups, judge their commercial and environmental potential, and find the funding or partners that can help them grow.

## Areas

- **Discover** — which startups deserve attention
- **Evaluate** — why they are promising, and what risks remain
- **Act** — which funding, investors, or partnerships could help them grow

## Run

1. Install Docker with Docker Compose.
2. Copy the environment file and set your OpenAI key:

   ```bash
   cp .env.example .env
   ```

   Put your key in `OPENAI_API_KEY` inside `.env`.

3. Start the app from the project root:

   ```bash
   docker compose up --build
   ```

4. Open [http://localhost:5173](http://localhost:5173).
