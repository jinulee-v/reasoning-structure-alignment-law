% ---------- Facts ----------
% bag(Id, Length, Width, Height, Weight).
bag(1, 22, 13,  6, 11).   % carry-on
bag(2, 41, 26, 18, 64).
bag(3, 44, 28, 22, 52).
bag(4, 35, 16, 14, 52).
bag(5, 41, 21, 16, 51).
bag(6, 37, 15, 11, 69).
bag(7, 50, 32, 28, 69).
bag(8, 44, 22, 18, 58).
bag(9, 33, 22,  9, 53).
bag(10,35, 19, 10, 51).
bag(11,36, 18,  9, 63).

flight_cost(215).                      % ticket price
route(europe_to_us).                   % Stockholm -> Austin
class(premium_economy).                % Michael's cabin class

% ---------- Helper rules ----------
dim_sum(Id, Sum) :-
    bag(Id, L, W, H, _),
    Sum is L + W + H.

carry_on(Id) :-                        % fits 22 x 14 x 9
    bag(Id, L, W, H, _),
    L =< 22, W =< 14, H =< 9.

% ---------- Oversize fees (Europe <-> U.S.) ----------
oversize_fee(Sum, 0)   :- Sum =< 62.
oversize_fee(Sum, 30)  :- Sum  > 62, Sum =< 65.
oversize_fee(Sum, 150) :- Sum  > 65, Sum =< 115.

% ---------- Over-weight fees (Europe <-> U.S.) ----------
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.

% ---------- Special fee per bag ----------
special_fee(Id, Fee) :-
    dim_sum(Id, Sum),
    bag(Id, _, _, _, W),
    oversize_fee(Sum, OSize),
    overweight_fee(W, OWeight),
    ( OSize >= OWeight -> Fee = OSize ; Fee = OWeight ).

% ---------- List of checked bags ----------
checked_bag_ids(Ids) :-
    findall(Id, (bag(Id, _, _, _, _), \+ carry_on(Id)), Ids).

% ---------- Base checked-bag fee ----------
% Premium Economy: 1st & 2nd bag free, 3rd & beyond $200 (Europe <-> U.S.)
base_fee(Index, 0)   :- Index =< 2.
base_fee(Index, 200) :- Index  > 2.

% ---------- Sum fees over all checked bags ----------
bags_total_cost(Total) :-
    checked_bag_ids(Ids),
    bags_total_cost(Ids, 1, Total).

bags_total_cost([], _, 0).
bags_total_cost([Id|Rest], Index, Total) :-
    special_fee(Id, Spec),
    base_fee(Index, Base),
    Next is Index + 1,
    bags_total_cost(Rest, Next, Tail),
    Total is Spec + Base + Tail.

% ---------- Grand total ----------
total_cost(Total) :-
    flight_cost(Flight),
    bags_total_cost(Bags),
    Total is Flight + Bags.

% ---------- Query ----------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.