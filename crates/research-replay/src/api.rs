//! Read-only W8 query helpers.

use crate::error::W8Error;
use crate::store::ReplayStore;
use crate::types::ReplayEvent;

pub fn events_for_game(store: &ReplayStore, game_id: &str) -> Result<Vec<ReplayEvent>, W8Error> {
    store.events_for_game(game_id)
}
