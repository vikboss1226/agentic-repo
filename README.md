# Agentic React Flow

A simple React app with a GitHub Actions CI pipeline, plus a small AI
agent that reacts when the build fails.

## What's in the app

`src/components/CommentsTable.js` fetches data from
`https://jsonplaceholder.typicode.com/posts/1/comments` with axios and
renders it as a simple HTML table (id, name, email, comment). `App.js`
just renders that component.

## CI pipeline (`.github/workflows/deploy.yml`)

Runs on every push or PR to `main`:

```
Checkout → Install Node → npm install → npm test → npm run build → upload build artifact
```

If that `build` job fails, a second job, `ai-fix`, runs automatically.

## The AI agent (`ai-agent/agent.py`)

One file, kept deliberately simple:

1. Pulls the log for whichever job failed, using the GitHub API.
2. If the log points at a specific file under `src/` (e.g. `src/App.js`),
   reads that file's actual current contents.
3. Sends the log — and the file contents, if it found one — to OpenAI
   (`gpt-4o-mini`) and asks it to diagnose the failure as JSON: a missing
   npm package, a fixable code error, or "unknown" if it isn't confident.
4. Acts on the diagnosis:
   - **Missing package** → `npm install <package>` on a new branch.
   - **Code error** → overwrites that one file with the model's corrected
     version, on a new branch. It only ever touches the exact file it
     already read — it can't invent a path to edit.
   - **Unknown** → does nothing and just logs the reason.
5. Either fix is pushed to a branch and opened as a PR back to `main`.

The agent never commits to `main` directly. Every fix, code or dependency,
lands as a PR a human reviews before merging. This means it can attempt
real code fixes now, not just dependency installs — but it will bail out
to "unknown" rather than guess at anything it isn't sure about.

**Secret required:** `OPENAI_API_KEY` (add it under repo Settings → Secrets
→ Actions). `GITHUB_TOKEN` is provided automatically by Actions.

## Try it

**Missing package:** remove `axios` from `package.json`'s dependencies
while `CommentsTable.js` still imports it, then push to `main`. The build
should fail on "Module not found: Can't resolve 'axios'", and you should
see a `fix/install-axios-*` branch and PR appear.

**Code error:** introduce an actual bug in `src/App.js` (e.g. a typo like
`<div classNam="App">` or a missing closing tag) and push. The build
should fail to compile, and `ai-fix` should open a `fix/code-*` branch and
PR with a corrected version of the file for you to review.

## Planned next steps

Deployment (e.g. AWS EC2) and more failure types for the agent to handle
come later, once this is solid.

---

# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)
