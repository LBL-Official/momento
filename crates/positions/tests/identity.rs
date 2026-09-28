use momento_core::{GameId, PositionId, StrategyId};
use momento_positions::GamePositionIndex;

#[test]
fn one_game_one_position_id() {
    let mut index = GamePositionIndex::new();
    let strategy = StrategyId::from_raw(1);
    let game = GameId::from_raw(42);
    let a = index.id_for(strategy, game);
    let b = index.id_for(strategy, game);
    assert_eq!(a, b);
}

#[test]
fn many_client_orders_share_position_id() {
    let mut index = GamePositionIndex::new();
    let strategy = StrategyId::from_raw(1);
    let game = GameId::from_raw(42);
    let position = index.id_for(strategy, game);
    let _order_a = momento_core::ClientOrderId::generate();
    let _order_b = momento_core::ClientOrderId::generate();
    let _order_c = momento_core::ClientOrderId::generate();
    assert_eq!(index.get(strategy, game), Some(position));
    assert!(
        index
            .register(strategy, game, PositionId::from_raw(999))
            .is_err()
    );
}

#[test]
fn different_games_have_different_positions() {
    let mut index = GamePositionIndex::new();
    let strategy = StrategyId::from_raw(1);
    let a = index.id_for(strategy, GameId::from_raw(1));
    let b = index.id_for(strategy, GameId::from_raw(2));
    assert_ne!(a, b);
}
