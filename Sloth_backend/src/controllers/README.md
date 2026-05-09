# Controllers
This folder contains the logic for handling HTTP requests.
When a route is hit, the controller function is called to extract the request data (req.body, req.params) and send the response (res.json).

**Rule:** Controllers should NOT contain complex business logic. They should call functions from the `services` folder.
