% ----------------------------
%  Facts that describe flight
% ----------------------------
ticket_price(88).

% itinerary : from(Origin) , to(Destination)
itinerary(port_au_prince, washington_dc).     % Port-au-Prince (Haiti)  -> U.S.A.
cabin(first).                                 % First-Class cabin

% All the checked pieces John wants to take
% bag(Id, Length, Width, Height, Weight).
bag(1,22,12,9 ,11).     % this one will become the carry-on, not checked
bag(2,37,21,18,55).
bag(3,35,18,12,66).
bag(4,34,19,11,53).
bag(5,38,14,11,69).
bag(6,46,30,22,71).
bag(7,37,16,11,53).
bag(8,42,24,19,66).
bag(9,50,36,24,51).
bag(10,44,25,21,62).
bag(11,49,34,26,89).

% ----------------------------
%  Helper predicates
% ----------------------------
% list of the 10 *checked* bags (bag #1 is carry-on and is ignored)
checked_bag_ids(Ids) :-
    findall(Id, (bag(Id,_,_,_,_), Id \= 1), Ids).

% linear size of a bag
size(Id,Linear) :-
    bag(Id,L,W,H,_),
    Linear is L+W+H.

% ----------------------------
%  Base bag-count fees
% ----------------------------
% Free for the first three checked pieces, 200 USD from the 4th onward
bag_count_fee(Index,0) :- Index =< 3, !.
bag_count_fee(_,200).

% ----------------------------
%  Oversize fees  (Haiti <-> U.S. = Caribbean route)
% ----------------------------
oversize_fee(Linear,Fee) :-
    Linear =< 62 , !, Fee = 0.
oversize_fee(Linear,30) :- Linear =< 65 , !.
oversize_fee(Linear,200).                     % 65 < size =< 115

% ----------------------------
%  Over-weight fees (Caribbean route)
% ----------------------------
overweight_fee(Weight,Limit,Fee) :-
    Weight =< Limit, !, Fee = 0.
overweight_fee(Weight,_,200) :- Weight > 70 , !.
overweight_fee(Weight,_,100) :- Weight > 53 , !.
overweight_fee(_,_,30).                      % 50 < wt =< 53

% ----------------------------
%  Total fee for ONE bag once we know which
%  3 bags are "free" (no bag-count charge)
% ----------------------------
bag_total_fee(Id,FreeList,Index,Fee) :-
    size(Id,Linear),
    bag(Id,_,_,_,Weight),
    (   member(Id,FreeList)      % weight allowance depends on it
    ->  WLimit = 70
    ;   WLimit = 50 ),
    oversize_fee(Linear,OSFee),
    overweight_fee(Weight,WLimit,OWFee),
    SpecialFee is max(OSFee,OWFee),
    bag_count_fee(Index,BaseFee),
    Fee is BaseFee + SpecialFee.

% ----------------------------
%  Sum the fees of all checked bags for one
%  particular choice of which 3 bags are free
% ----------------------------
bags_total(FreeList,Total) :-
    checked_bag_ids(Ids),
    bags_total(Ids,FreeList,1,0,Total).

bags_total([],_,_,Acc,Acc).
bags_total([Id|Rest],Free,Idx,Acc,Total) :-
    bag_total_fee(Id,Free,Idx,BFee),
    Idx1 is Idx + 1,
    Acc1 is Acc + BFee,
    bags_total(Rest,Free,Idx1,Acc1,Total).

% ----------------------------
%  Generate all 3-element combinations
% ----------------------------
combination(0,_,[]).
combination(K,[H|T],[H|R]) :-
    K>0, K1 is K-1,
    combination(K1,T,R).
combination(K,[_|T],R) :-
    K>0,
    combination(K,T,R).

all_three_free_sets(Sets) :-
    checked_bag_ids(Ids),
    findall(Set, combination(3,Ids,Set), Sets).

% ----------------------------
%  Minimum baggage cost over every way of
%  picking which 3 bags get the free allowance
% ----------------------------
minimum_baggage_cost(MinCost) :-
    all_three_free_sets(Sets),
    findall(Cost,
            (member(Free,Sets), bags_total(Free,Cost)),
            Costs),
    min_list(Costs,MinCost).

% ----------------------------
%  Grand total (ticket + bags)
% ----------------------------
total_cost(Total) :-
    ticket_price(Tix),
    minimum_baggage_cost(Bags),
    Total is Tix + Bags.

% ----------------------------
%  Query - print result
% ----------------------------
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.