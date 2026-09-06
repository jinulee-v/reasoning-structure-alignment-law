/*************************************************************************
*  Rules needed for the present case (American Airlines statutes)        *
*************************************************************************/

% ---------- Free carry-on limits ---------------------------------------
carry_on_dimensions(22,14,9).

% A given bag is a free carry-on when it is within the carry-on cube
carry_on(_Id,L,W,H,_Wt) :-
    carry_on_dimensions(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

% ---------- Extra charges (oversize / overweight) for U.S. <-> Mexico ----

% Oversize fee (sum of the 3 outside dimensions)
oversize_fee(L,W,H,Fee) :-
    Sum is L+W+H,
    (   Sum > 65  -> Fee = 200           %  > 65 in - 115 in
    ;   Sum > 62  -> Fee = 30            %  > 62 in - 65 in
    ;   Fee = 0).

% Over-weight fee
overweight_fee(Wt,Fee) :-
    (   Wt > 70  -> Fee = 200            %  70 - 100 lbs
    ;   Wt > 53  -> Fee = 100            %  53 - 70  lbs
    ;   Wt > 50  -> Fee = 30             %  50 - 53  lbs
    ;   Fee = 0).

% The higher of the two applies in addition to the checked-bag fee
extra_fee(L,W,H,Wt,Extra) :-
    oversize_fee(L,W,H,OS),
    overweight_fee(Wt,OW),
    (OS >= OW -> Extra = OS ; Extra = OW).

% ---------- Base checked-bag fee (Main Cabin, U.S. <-> Mexico) -----------
base_fee(1,35).    % 1st checked bag
base_fee(2,45).    % 2nd checked bag
base_fee(N,200) :- % 3rd bag and beyond
    N >= 3.

% ---------- Facts for Susan's trip -------------------------------------
ticket_price(150).

% bag(Id,Length,Width,Height,Weight)
bag(1,21,13, 8,10).   % backpack  (carry-on)
bag(2,35,16,13,58).
bag(3,35,18,12,96).
bag(4,34,18,11,52).
bag(5,34,19,12,77).
bag(6,46,24,24,84).

/*************************************************************************
*  Auxiliary predicates                                                  *
*************************************************************************/

sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S0), S is H+S0.

assign_indices([],_,[]).
assign_indices([Bag|Rest],N,[idx(Bag,N)|Out]) :-
    N1 is N+1,
    assign_indices(Rest,N1,Out).

% Cost of a single checked bag once its sequential position is known
bag_cost(Index,Id,Cost) :-
    bag(Id,L,W,H,Wt),
    base_fee(Index,Base),
    extra_fee(L,W,H,Wt,Extra),
    Cost is Base + Extra.

/*************************************************************************
*  Main predicate that yields Susan's total travel cost                  *
*************************************************************************/

total_cost(Total) :-
    ticket_price(Ticket),

    % Collect bags that are NOT free carry-ons
    findall(Id,
            (bag(Id,L,W,H,Wt), \+ carry_on(Id,L,W,H,Wt)),
            CheckedBagsUnordered),

    % Keep them in ascending Id order (2,3,4,5,6)
    sort(CheckedBagsUnordered, CheckedBags),
    assign_indices(CheckedBags,1,IndexedBags),

    % Compute fees for each checked bag
    findall(Cost,
            (member(idx(Id,Idx),IndexedBags), bag_cost(Idx,Id,Cost)),
            BagCosts),
    sum_list(BagCosts,TotalBagFees),

    Total is Ticket + TotalBagFees.

/*************************************************************************
*  Query demanded in the assignment                                      *
*************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.