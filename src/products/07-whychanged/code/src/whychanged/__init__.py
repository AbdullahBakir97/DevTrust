"""WhyChanged - production diff-detective.

When monitoring tells you something broke, the obvious next question is
"what changed?" -- and the answer is rarely just "the latest deploy."
WhyChanged correlates a configurable set of change sources (commits,
deploys, feature-flag toggles, dependency bumps, infra config diffs) in
a given time window and ranks them by likelihood of having caused the
incident.

Wave 3 product. v0.0.1 ships the engine + the local Git provider; cloud
provider plugins (LaunchDarkly, Render, Vercel, GitHub deployments)
land in v0.1+.
"""

__version__ = "0.1.0"
