# Public source capture log

Capture date: **13 October 2026** (India store listing)

## Google Play — Employee App

- Listing: https://play.google.com/store/apps/details?hl=en_IN&id=com.moveinsync.ets
- Displayed rating: **4.3 stars**
- Displayed review count: **1.15L reviews** (rounded public display; exact count was not exposed in the page capture)
- Listing's visible last-updated date: **8 October 2026**
- Latest visible release-history label captured: **10.50.0**, dated **5 October 2026**

The previous figure of **4.64 from 114,880** is not used because it did not match this live listing capture. Ratings and listing metadata change, so refresh them before reusing the figure.

## Rating methodology

Google's public Play rating methodology states that the rating shown to users is weighted toward more recent ratings: https://support.google.com/googleplay/android-developer/answer/138230?hl=en-IN

This helps explain why a store rating and the average of a self-selected written-review sample are not the same metric. It does not make the written-review sample representative of all users.

## iOS contextual check

- Listing: https://apps.apple.com/in/app/moveinsync/id962949521?platform=iphone
- Displayed rating on 13 October 2026: **4.7/5 from 60k ratings** (both are rounded display values).

This is directional context only; it is not a controlled comparison with Google Play because platform populations, versions and rating mechanics can differ.

## Scope caveat

The frozen dataset was collected on 13 October 2026 using `google-play-scraper` with `lang="en"` and `country="in"`. Hindi and other regional-language review texts were not separately collected or counted. The version label `12.19.0` in review metadata does not reconcile with the `10.50.0` release-history label seen on the live page; do not associate review spikes with a specific release until engineering maps the labels to actual production builds and rollout dates.
