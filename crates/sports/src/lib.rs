//! Sport domain crate. One crate; sport folders are modules, not nested crates.
//!
//! Generic infrastructure (execution, risk, Kalshi) must not live here.

#![forbid(unsafe_code)]

pub mod mlb;
pub mod nba;
pub mod ncaab;
pub mod nfl;
pub mod wnba;

use momento_core::GameId;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SportId {
    Mlb,
    Nba,
    Ncaab,
    Nfl,
    Wnba,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SportGame {
    pub sport: SportId,
    pub game_id: GameId,
}
