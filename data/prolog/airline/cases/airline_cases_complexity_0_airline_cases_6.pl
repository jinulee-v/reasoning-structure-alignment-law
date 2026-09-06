% -------------------------------
%  Statutory rules (abridged)
% -------------------------------

% oversize_fee(RouteGroup, DimSum, Fee)
% China group
oversize_fee(china, DimSum, 0  ) :- DimSum =< 62, !.
oversize_fee(china, DimSum, 30 ) :- DimSum =< 65, !.
oversize_fee(china, DimSum, 200) :- DimSum =< 115.

% overweight_fee(RouteGroup, Weight, Fee)
% China group
overweight_fee(china, W, 0  ) :- W =< 50, !.
overweight_fee(china, W, 30 ) :- W =< 53, !.
overweight_fee(china, W, 100) :- W =< 70, !.
overweight_fee(china, W, 450) :- W =< 100.

% The charge that applies to a bag is the HIGHER of the two
bag_extra_fee(Route, DimSum, Weight, Fee) :-
    oversize_fee(Route, DimSum, OS),
    overweight_fee(Route, Weight, OW),
    (OS >= OW -> Fee = OS ; Fee = OW).

% -------------------------------
%  Karen's facts
% -------------------------------

route(china).               % Wuhan (China) -> Portland (USA)

% checked_bag(Name, L, W, H, Weight)
checked_bag(bag1, 43,27,17,52).   % 87 in, 52 lbs
checked_bag(bag2, 49,30,23,52).   % 102 in, 52 lbs
checked_bag(bag3, 37,18, 9,60).   % 64 in, 60 lbs
checked_bag(bag4, 35,17,13,53).   % 65 in, 53 lbs

flight_ticket_cost(1284).

% --------------------------------
%  Base checked-bag fees for Karen
% --------------------------------
% Karen is Main Cabin, to / from China
% 1st bag $0, 2nd $100, 3rd $200, 4th $200
base_fees([0,100,200,200]).

% --------------------------------
%  Helper predicates
% --------------------------------
dim_sum(L,W,H,S) :- S is L+W+H.

bag_overcharge(Bag, Charge) :-
    checked_bag(Bag,L,W,H,Weight),
    dim_sum(L,W,H,Sum),
    route(Route),
    bag_extra_fee(Route, Sum, Weight, Charge).

all_overcharges(List) :-
    findall(C, bag_overcharge(_,C), List).

% pair the largest over-charge with the smallest base fee
pair_costs(BaseList, OverList, Costs) :-
    msort(BaseList, BAsc),
    msort(OverList, OAsc),
    reverse(OAsc, ODesc),        % now descending
    pair_costs_(BAsc, ODesc, Costs).
pair_costs_([],[],[]).
pair_costs_([B|Bs],[O|Os],[C|Cs]) :-
    C is B + O,
    pair_costs_(Bs,Os,Cs).

checked_bags_total(Total) :-
    base_fees(Base),
    all_overcharges(Over),
    pair_costs(Base,Over,Costs),
    sum_list(Costs, Total).

total_cost(Total) :-
    flight_ticket_cost(Tix),
    checked_bags_total(Bags),
    Total is Tix + Bags.

% -------------------------------
%  Query
% -------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.