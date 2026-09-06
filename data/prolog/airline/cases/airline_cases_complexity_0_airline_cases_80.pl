:- use_module(library(lists)).

% basic facts about the itinerary ----------------------------------------------

route(within_usa).                     % Salt Lake City -> Chicago
cabin(first).                           % First Class
flight_cost(247).                      % price of the ticket (USD)

% ------------------------------------------------------------------------------
% BAG FACTS  bag(Id,Length,Width,Height,Weight)
% ------------------------------------------------------------------------------

bag(b1,20,12, 6,  9).   % 20 x 12 x  6 - fits as carry-on
bag(b2,39,27,17, 68).   % checked
bag(b3,35,19,10, 52).   % checked
bag(b4,42,21,14, 65).   % checked
bag(b5,39,13,15, 51).   % checked

% ------------------------------------------------------------------------------
% 1.  Which bags must be checked?
% ------------------------------------------------------------------------------

carry_on_limits(22,14,9).

carry_on(ID) :-
    bag(ID,L,W,H,_),
    carry_on_limits(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

checked_bag(ID) :- bag(ID,_,_,_,_), \+ carry_on(ID).

checked_bags(L) :- findall(ID,checked_bag(ID),L).

% ------------------------------------------------------------------------------
% 2.  Size / weight helpers
% ------------------------------------------------------------------------------

linear_size(ID,Size) :-
    bag(ID,L,W,H,_),
    Size is L + W + H.

% ---------------------------------------------------------------------
%  Oversize fees (within the U.S.)
% ---------------------------------------------------------------------

oversize_fee(Size,0)      :- Size =< 62.
oversize_fee(Size,30)     :- Size  > 62, Size =< 65.
oversize_fee(Size,200)    :- Size  > 65, Size =< 115.

% ---------------------------------------------------------------------
%  Over-weight fees (within the U.S.)
% ---------------------------------------------------------------------

% complimentary (1st & 2nd) - up to 70 lb free
overweight_free(W,0)      :- W =< 70.
overweight_free(W,inf)    :- W  > 70.          % not accepted (give big cost)

% charged (3rd, 4th ...)
overweight_charged(W,0)   :- W =< 50.
overweight_charged(W,30)  :- W  > 50, W =< 53.
overweight_charged(W,100) :- W  > 53, W =< 70.
overweight_charged(W,inf) :- W  > 70.          % not accepted

% choose the higher of the two surcharges that apply
surcharge(ID,Type,Fee) :-
    linear_size(ID,Sz), oversize_fee(Sz,SizeFee),
    bag(ID,_,_,_,Wt),
    ( Type = complimentary ->
        overweight_free(Wt,WtFee)
    ; overweight_charged(Wt,WtFee)
    ),
    ( SizeFee == inf ; WtFee == inf ->
        Fee = inf
    ; max_member(Fee,[SizeFee,WtFee])
    ).

% ---------------------------------------------------------------------
%  Bag-position fees for First Class (domestic)
% ---------------------------------------------------------------------

bag_position_fee(3,150).
bag_position_fee(N,200) :- N >= 4.

% ---------------------------------------------------------------------
%  Cost of a single bag
% ---------------------------------------------------------------------

bag_cost(ID,complimentary,_,Cost) :-
    surcharge(ID,complimentary,S),
    ( S == inf -> Cost = inf ; Cost = S ).

bag_cost(ID,charged,Position,Cost) :-
    bag_position_fee(Position,BagFee),
    surcharge(ID,charged,S),
    ( S == inf -> Cost = inf ; Cost is BagFee + S ).

% ---------------------------------------------------------------------
%  Cost of a whole plan  (which two of the four bags are free)
% ---------------------------------------------------------------------

combination_of_two(List,[A,B]) :-
    select(A,List,R), select(B,R,_), A @< B.

plan_cost(FreeList,TotalCost) :-
    checked_bags(Chk),
    subtract(Chk,FreeList,PayBags),

    % costs of the free bags
    findall(CF,(member(B,FreeList),bag_cost(B,complimentary,0,CF)),FreeCosts),
    sum_list(FreeCosts,FreeSum),

    % evaluate every order of the charged bags (3rd / 4th)
    findall(T,(  permutation(PayBags,[B3,B4]),
                 bag_cost(B3,charged,3,C1),
                 bag_cost(B4,charged,4,C2),
                 (C1 == inf ; C2 == inf -> T = inf ; T is C1 + C2)
               ),Totals),
    min_list(Totals,MinCharged),

    ( FreeSum == inf ; MinCharged == inf ->
        TotalCost = inf
    ; TotalCost is FreeSum + MinCharged).

% ---------------------------------------------------------------------
%  Minimal bag cost over all possibilities
% ---------------------------------------------------------------------

min_bag_cost(Min) :-
    checked_bags(Chk),
    findall(Cost,(combination_of_two(Chk,Free),plan_cost(Free,Cost)),Costs),
    min_list(Costs,Min).

% ---------------------------------------------------------------------
%  Overall total
% ---------------------------------------------------------------------

total_cost(Total) :-
    flight_cost(Fare),
    min_bag_cost(BagFees),
    Total is Fare + BagFees.

% ---------------------------------------------------------------------
%  Query asked for by the problem statement
% ---------------------------------------------------------------------

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.