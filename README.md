# boloo_shipments

### End points
- `/sellars` suports create & list
  - It will check whethet the credentials are valid or not before saving.
- `/sellars/<int>/` supports retrieve, update & delete.
  - Upon deleting all related data will be deleted (Cascade).
- `sellars/<ini>/sync` will add records to table to start syncing.
- `/sellars/<int>/shipments/` will show all the shipment details.
  - Initially it will show empty list.
  - When shipments list api from bol website fetched it will show as data not yet fetched.
  - After detail apis fetched it will contain full shipment details.


### High Level data fetching design
- In this app there are 3 main tasks which will run for every minute.
- `refresh_tokens` will refreshes the token & stores new expiry date for all records whose expiry date less or equal to now.
- `sync_shipments` will sync all shipments from bol.
- `sync_detail_shipments` will fetch the detailed data of the shipments if not already fetched.
