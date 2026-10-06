# Scan books

The library supports a scan of the ISBN barcode on the back of each book with the camera
of a phone. Each scan adds the book to the shelf that you select, with the details and
the cover from [Open Library](https://openlibrary.org). Use it to fill a shelf in 1 pass.

![A shelf scan on a phone with 3 results](../../images/scan-mobile.png)

## Scan a shelf

1. Open the **Library** tab on a phone, and select **Scan books**. Or select **Scan** on a
   shelf in [Rooms and shelves](rooms-and-shelves.md).
2. Select the room and the shelf.
3. Select the method **Scan barcodes**, then select **Start scan** to open the camera.
4. Put the barcode of a book in the frame. The result shows under the camera.
5. Do step 4 again for each book on the shelf.
6. Select **Next shelf** to go on with the next shelf, or **Done** to see the summary.

If the light is low and the phone has a torch, select **Light**.

## Enter an ISBN

Use **Enter ISBN** for a book with no barcode, or on a computer with no camera.

1. Select the method **Enter ISBN**.
2. Type the ISBN-10 or the ISBN-13, and press Enter.

The library accepts an ISBN with or without hyphens. It checks the check digit, and shows
**This is not a valid ISBN.** for a typing error.

## Results

| Result | What it means |
|---|---|
| **Added** | The book and a copy on this shelf are in the library. |
| **Already in** *place* | The library has a copy of the book on another shelf. |
| **No match** | Open Library has no book with this ISBN. Select **Add details** to type the title and the authors. |

For a book that is already in the library, select 1 of these:

- **Move here**: move the copy to this shelf.
- **Add 2nd copy**: add 1 more copy on this shelf.
- **Skip**: change nothing.

If Open Library does not answer, the library saves the book with its ISBN and tries
again later. The book shows **Needs details** until the details arrive.

## Summary

![The summary of a shelf scan on a phone](../../images/scan-summary-mobile.png)

**Done** shows the summary of the scan: the books that the scan added and moved, and the
books that need details. Select **Set status to Read for me** to set the status Read for
your person on each book that the scan added or moved.

## Borrowed books

On the **Loans** page, select **Scan borrowed books** to scan books that you borrow,
such as library books. Each scan adds a [loan](loans.md) with no copy.

## Camera and HTTPS

The browser gives the camera only to a page with an HTTPS address. On an `http://`
address, **Scan barcodes** shows the message **The camera needs HTTPS**. You cannot start
a camera scan there. Select **Enter ISBN** to add books without the camera.

![The scan setup on a page with an http address](../../images/scan-https-mobile.png)

To use the camera, open Home Assistant with an HTTPS address, such as Home Assistant
Cloud or a reverse proxy with a certificate. The Home Assistant phone app uses the
internal URL on your home network and the external URL away from home. If the camera
works only away from home, set the internal URL in the app to an HTTPS address too.

If the browser asks for the camera, allow it. If the browser cannot read barcodes, the
library loads a barcode reader of its own the first time.
