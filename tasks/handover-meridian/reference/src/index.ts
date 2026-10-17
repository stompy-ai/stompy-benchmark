import { createApp } from './app.js';
const port = Number(process.env.PORT ?? 3000);
createApp(process.env.MERIDIAN_DB ?? ':memory:').listen(port, () => console.log(`meridian listening on ${port}`));
