/* ---------------  Statutory rules that apply to this case --------------- */

/* ticket price ----------------------------------------------------------- */
ticket_price(197).

/* route type - Minneapolis -> Orlando is wholly within the U.S. ----------- */
route(within_us).

/* passenger class -------------------------------------------------------- */
class(first).

/* complimentary-bag allowance for a Domestic First customer -------------- */
complimentary_checked_bags(2).          /* first 2 checked bags are free   */
complimentary_weight_limit(70).         /* up to 70 lbs for free bags       */

/* checked-bag fees (after the 2 free ones) for a domestic itinerary ------ */
checked_bag_fee(3,150).                /* 3rd bag                          */
checked_bag_fee(Number,200) :-         /* 4th bag and higher               */
    Number  > 3.

/* oversize fees within the U.S. ----------------------------------------- */
oversize_fee(Dim,0)   :- Dim =< 62.
oversize_fee(Dim,30)  :- Dim > 62, Dim =< 65.
oversize_fee(Dim,200) :- Dim > 65, Dim =< 115.

/* domestic overweight fees ---------------------------------------------- */
/* Note: limit is 70 lbs for complimentary bags, 50 lbs for charged bags   */

overweight_fee(free,   W,0)   :- W =< 70.
overweight_fee(free,   W,200) :- W > 70,  W =< 100.

overweight_fee(charged,W,0)   :- W =< 50.
overweight_fee(charged,W,30)  :- W  > 50, W =< 53.
overweight_fee(charged,W,100) :- W  > 53, W =< 70.
overweight_fee(charged,W,200) :- W  > 70, W =< 100.

/* when a bag is both oversize and overweight, only the higher fee counts  */
bag_special_fee(Status,Dim,W,F) :-
    oversize_fee(Dim,OS),
    overweight_fee(Status,W,OW),
    (OS >= OW -> F = OS ; F = OW).

/* -----------------------  Facts of the concrete case  ------------------ */

% bag(Id, Length, Width, Height, Weight).
bag(2,48,35,26,86).
bag(3,46,23,18,68).
bag(4,35,17,13,62).
bag(5,36,17,10,75).
bag(6,34,16,13,51).
bag(7,47,31,23,59).
bag(8,51,25,26,79).

/* one backpack 22x12x7 (8 lbs) is the free carry-on - no fact required   */

/* ----------------------  Auxiliary predicates -------------------------- */

dimension_sum(Id,Sum) :-
    bag(Id,L,W,H,_),
    Sum is L+W+H.

weight(Id,W) :-
    bag(Id,_,_,_,W).

/* list of all checked-bag IDs */
bag_ids(Ids) :- findall(Id, bag(Id,_,_,_,_), Ids).

/* choose any 2 distinct elements from a list (order-independent) */
choose_two(List,A,B) :-
    append(_, [A|Rest], List),
    member(B, Rest).

/* count members in a list ------------------------------------------------ */
count(List,N) :- length(List,N).

/* compute all fees for a concrete choice of the 2 complimentary bags ----- */
fees_for_choice(FreeIDs, TotalSpecial, CheckedBagFee) :-
    % split bags into free vs charged
    bag_ids(All), subtract(All,FreeIDs,ChargedIDs),

    % ---------- special (oversize / overweight) fees --------------------
    % free bags
    findall(F,
        (member(Id,FreeIDs),
         dimension_sum(Id,Dim),
         weight(Id,W),
         bag_special_fee(free,Dim,W,F)),
        FreeFees),
    % charged bags
    findall(F,
        (member(Id,ChargedIDs),
         dimension_sum(Id,Dim),
         weight(Id,W),
         bag_special_fee(charged,Dim,W,F)),
        ChargedFees),
    append(FreeFees,ChargedFees,AllFees),
    sum_list(AllFees,TotalSpecial),

    % ---------- checked-bag fees (based only on how many are charged) ----
    count(ChargedIDs,NCharged),
    ( NCharged =:= 0 ->
        CheckedBagFee = 0
    ;   checked_bag_fee(3,ThirdFee),        % always one "third" bag
        Remaining is NCharged - 1,
        CheckedBagFee is ThirdFee + Remaining*200
    ).

/* compute total trip cost for a particular free-bag choice -------------- */
total_for_choice(FreeIDs,TotalCost) :-
    fees_for_choice(FreeIDs,Special,BagFees),
    ticket_price(Ticket),
    TotalCost is Ticket + Special + BagFees.

/* ---------------------------  Main goal -------------------------------- */

total_cost(MinTotal) :-
    bag_ids(Ids),
    % pick every possible pair of complimentary bags
    setof(Total,
          A^B^FreeIDs^(
              choose_two(Ids,A,B),
              FreeIDs = [A,B],
              total_for_choice(FreeIDs,Total)
          ),
          Totals),
    min_list(Totals,MinTotal).

/* ---------------------------  Output ----------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.