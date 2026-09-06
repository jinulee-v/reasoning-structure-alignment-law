/* Case facts */
flight_cost(159).
passenger_class(business).
route(within_us).

/* bag(Id, Length, Width, Height, Weight) */
bag(1, 19, 13, 8, 10).
bag(2, 43, 19, 19, 84).
bag(3, 35, 16, 12, 52).
bag(4, 50, 28, 25, 52).
bag(5, 37, 13, 14, 69).

/* Cabin allowances */
personal_item_limit(18, 14, 8).
carry_on_limit(22, 14, 9).

fits_personal_item(Id) :-
    bag(Id, L, W, H, _),
    personal_item_limit(MaxL, MaxW, MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

fits_carry_on(Id) :-
    bag(Id, L, W, H, _),
    carry_on_limit(MaxL, MaxW, MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

allowed_in_cabin(Id) :-
    fits_personal_item(Id).
allowed_in_cabin(Id) :-
    fits_carry_on(Id).

checked_bag_ids(Ids) :-
    findall(Id, (bag(Id, _, _, _, _), \+ allowed_in_cabin(Id)), Ids).

/* Region-specific checked bag base fees for Business */
checked_bag_base_fee(within_us, business, 1, 0).
checked_bag_base_fee(within_us, business, 2, 0).
checked_bag_base_fee(within_us, business, 3, 150).
checked_bag_base_fee(within_us, business, N, 200) :-
    N >= 4.

/* Business customers get 1st and 2nd checked bags complimentary */
complimentary_checked_bags(business, 2).

/* Helpers */
dimension_sum(L, W, H, Sum) :-
    Sum is L + W + H.

/* Oversize fee for within/between U.S., Canada, Puerto Rico, U.S. Virgin Islands */
oversize_fee(within_us, Sum, 0) :-
    Sum =< 62.
oversize_fee(within_us, Sum, 30) :-
    Sum > 62,
    Sum =< 65.
oversize_fee(within_us, Sum, 200) :-
    Sum > 65,
    Sum =< 115.

/* Overweight fee depends on whether bag is complimentary or excess-charged */
overweight_fee(within_us, complimentary, Weight, 0) :-
    Weight =< 70.
overweight_fee(within_us, complimentary, Weight, 200) :-
    Weight > 70,
    Weight =< 100.

overweight_fee(within_us, charged, Weight, 0) :-
    Weight =< 50.
overweight_fee(within_us, charged, Weight, 30) :-
    Weight > 50,
    Weight =< 53.
overweight_fee(within_us, charged, Weight, 100) :-
    Weight > 53,
    Weight =< 70.
overweight_fee(within_us, charged, Weight, 200) :-
    Weight > 70,
    Weight =< 100.

/* Penalty is higher of oversize and overweight */
bag_penalty(Id, BagStatus, Penalty) :-
    route(Route),
    bag(Id, L, W, H, Weight),
    dimension_sum(L, W, H, Sum),
    oversize_fee(Route, Sum, OversizeFee),
    overweight_fee(Route, BagStatus, Weight, OverweightFee),
    Penalty is max(OversizeFee, OverweightFee).

/* Choose which checked bags should use the complimentary allowance:
   to minimize total cost, assign complimentary slots to the bags with
   the greatest savings from complimentary weight allowance. */
bag_saving_if_complimentary(Id, Saving) :-
    bag_penalty(Id, complimentary, CompPenalty),
    bag_penalty(Id, charged, ChargedPenalty),
    Saving is ChargedPenalty - CompPenalty.

insert_by_saving(Id-S, [], [Id-S]).
insert_by_saving(Id-S, [Id2-S2|Rest], [Id-S,Id2-S2|Rest]) :-
    S >= S2.
insert_by_saving(Id-S, [Id2-S2|Rest], [Id2-S2|SortedRest]) :-
    S < S2,
    insert_by_saving(Id-S, Rest, SortedRest).

sort_by_saving([], []).
sort_by_saving([Pair|Rest], Sorted) :-
    sort_by_saving(Rest, SortedRest),
    insert_by_saving(Pair, SortedRest, Sorted).

take(0, _, []).
take(_, [], []).
take(N, [X|Xs], [X|Ys]) :-
    N > 0,
    N1 is N - 1,
    take(N1, Xs, Ys).

member_id(Id, [Id-_|_]).
member_id(Id, [_|Rest]) :-
    member_id(Id, Rest).

complimentary_bag(Id) :-
    passenger_class(Class),
    complimentary_checked_bags(Class, Count),
    checked_bag_ids(Checked),
    findall(B-S, (member(B, Checked), bag_saving_if_complimentary(B, S)), Pairs),
    sort_by_saving(Pairs, Sorted),
    take(Count, Sorted, Top),
    member_id(Id, Top).

bag_status(Id, complimentary) :-
    complimentary_bag(Id), !.
bag_status(_, charged).

/* Keep original checked bag order for 1st/2nd/3rd/4th bag numbering */
sum_checked_costs([], _, 0).
sum_checked_costs([Id|Rest], Index, Total) :-
    passenger_class(Class),
    route(Route),
    bag_status(Id, Status),
    checked_bag_base_fee(Route, Class, Index, BaseFee),
    bag_penalty(Id, Status, Penalty),
    NextIndex is Index + 1,
    sum_checked_costs(Rest, NextIndex, RestTotal),
    Total is BaseFee + Penalty + RestTotal.

compute_total(Cost) :-
    flight_cost(Flight),
    checked_bag_ids(Checked),
    sum_checked_costs(Checked, 1, BagTotal),
    Cost is Flight + BagTotal.

:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.