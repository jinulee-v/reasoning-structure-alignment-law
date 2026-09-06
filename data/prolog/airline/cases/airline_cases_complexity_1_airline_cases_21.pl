/* Case facts */

flight_origin(quito).
flight_destination(salt_lake_city).
flight_region(ecuador_us).
flight_class(main_cabin).
flight_ticket_price(560).

passenger(william).

item(1, backpack, 20, 13, 7, 9).
item(2, backpack, 41, 21, 19, 51).
item(3, backpack, 36, 17, 12, 65).
item(4, luggage_box, 37, 20, 11, 85).
item(5, luggage_box, 51, 25, 27, 52).
item(6, luggage_box, 38, 17, 13, 63).
item(7, luggage_box, 35, 21, 15, 52).
item(8, backpack, 33, 22, 9, 90).

/* Size helpers */

linear_size(L, W, H, S) :- S is L + W + H.

fits_personal_item(L, W, H) :-
    L =< 18, W =< 14, H =< 8.

fits_carry_on(L, W, H) :-
    L =< 22, W =< 14, H =< 9.

personal_item(Id) :-
    item(Id, _, L, W, H, _),
    fits_personal_item(L, W, H).

carry_on_candidate(Id) :-
    item(Id, _, L, W, H, _),
    fits_carry_on(L, W, H).

checked_item(Id) :-
    item(Id, _, _, _, _, _),
    \+ personal_item(Id),
    \+ (carry_on_candidate(Id), Id \= 1).

/* In this case the smallest qualifying bag is used as the personal item.
   No other item qualifies as a carry-on, so all remaining items are checked. */
personal_item(1).

/* Checked bag ordering follows the remaining listed items */
checked_bag_order(1, 2).
checked_bag_order(2, 3).
checked_bag_order(3, 4).
checked_bag_order(4, 5).
checked_bag_order(5, 6).
checked_bag_order(6, 7).
checked_bag_order(7, 8).

/* Free checked bag allowance */
free_checked_bags(ecuador_us, main_cabin, 1).

/* Base checked bag fees for this region/cabin */
base_checked_bag_fee(ecuador_us, main_cabin, BagNumber, 0) :-
    free_checked_bags(ecuador_us, main_cabin, Free),
    BagNumber =< Free.
base_checked_bag_fee(ecuador_us, main_cabin, 2, 100).
base_checked_bag_fee(ecuador_us, main_cabin, N, 200) :-
    N >= 3.

/* Oversize fees: Panama / Colombia / Ecuador / Peru and U.S. => South America (except Guyana/Suriname) band */
oversize_fee(ecuador_us, Size, 0) :-
    Size =< 62.
oversize_fee(ecuador_us, Size, 30) :-
    Size > 62,
    Size =< 65.
oversize_fee(ecuador_us, Size, 150) :-
    Size > 65,
    Size =< 115.

/* Overweight fees for Central America/South America <-> U.S. */
overweight_fee(ecuador_us, Weight, 0) :-
    Weight =< 50.
overweight_fee(ecuador_us, Weight, 30) :-
    Weight > 50,
    Weight =< 53.
overweight_fee(ecuador_us, Weight, 100) :-
    Weight > 53,
    Weight =< 70.
overweight_fee(ecuador_us, Weight, 200) :-
    Weight > 70,
    Weight =< 100.

/* Per checked bag total: checked-bag fee + higher of oversize/overweight */
checked_bag_fee(BagNumber, ItemId, Fee) :-
    checked_bag_order(BagNumber, ItemId),
    item(ItemId, _, L, W, H, Weight),
    linear_size(L, W, H, Size),
    flight_region(Region),
    flight_class(Class),
    base_checked_bag_fee(Region, Class, BagNumber, BaseFee),
    oversize_fee(Region, Size, OversizeFee),
    overweight_fee(Region, Weight, OverweightFee),
    ExtraFee is max(OversizeFee, OverweightFee),
    Fee is BaseFee + ExtraFee.

bags_total(Total) :-
    findall(Fee, checked_bag_fee(_, _, Fee), Fees),
    sum_list(Fees, Total).

special_needs_cost(0).

compute_total(Cost) :-
    flight_ticket_price(Ticket),
    bags_total(Bags),
    special_needs_cost(Special),
    Cost is Ticket + Bags + Special.

:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.